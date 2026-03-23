import argparse
import csv
import json
import os
import sys
import unicodedata
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

SUPABASE_URL = "https://mynxlubykylncinttggu.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6"
    "Im15bnhsdWJ5a3lsbmNpbnR0Z2d1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUxODg2NzAs"
    "ImV4cCI6MjA4MDc2NDY3MH0.Z-zqiD6_tjnF2WLU167z7jT5NzZaG72dWH0dpQW1N-Y"
)
IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
CORRECAO_URL = "https://mynxlubykylncinttggu.functions.supabase.co/ibge-submit"
BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "input.csv"
OUTPUT_CSV = BASE_DIR / "resultado.csv"
STATS_JSON = BASE_DIR / "stats.json"
TIMEOUT = 60


class AppError(Exception):
    pass

#Normaliza o texto, removendo espaço, deixando todo minúsculo, removendo acento... Dessa maneira fica mais fácil analisar.
def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    allowed = []
    for ch in text:
        if ch.isalnum() or ch.isspace():
            allowed.append(ch)
    return " ".join("".join(allowed).split())

#Criação de usuário na Supabase 
def signup(email: str, password: str, nome: str) -> dict:
    url = f"{SUPABASE_URL}/auth/v1/signup"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
    }
    payload = {
        "email": email,
        "password": password,
        "data": {"nome": nome},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()

#Faz login e pega o token de acesso
def login(email: str, password: str) -> str:
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
    }
    payload = {"email": email, "password": password}
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise AppError("Não foi possível obter o access_token no login.")
    return token

#Baixa os dados do IBGE, fazendo um GET e validando a lista
def fetch_ibge_municipios() -> List[dict]:
    response = requests.get(IBGE_MUNICIPIOS_URL, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise AppError("Resposta inesperada da API do IBGE.")
    return data

#Cria uma busca, tendo em vista que a lista é extensa e podemos ter mais de um municipio com o mesmo nome
def build_index(municipios: List[dict]) -> Tuple[Dict[str, List[dict]], List[str]]:
    index: Dict[str, List[dict]] = defaultdict(list)
    for item in municipios:
        nome = item.get("nome", "")
        key = normalize_text(nome)
        index[key].append(item)
    return dict(index), list(index.keys())

#Pega os dados que nos interessam do JSON do IBGE
def extract_fields(item: dict) -> dict:
    microrregiao = item.get("microrregiao", {})
    mesorregiao = microrregiao.get("mesorregiao", {})
    uf = mesorregiao.get("UF", {})
    regiao = uf.get("regiao", {})
    return {
        "municipio_ibge": item.get("nome", ""),
        "uf": uf.get("sigla", ""),
        "regiao": regiao.get("nome", ""),
        "id_ibge": item.get("id", ""),
    }

#Escolhe um municipio, caso exista mais de um com mesmo nome, com base no ID
def pick_exact_match(matches: List[dict]) -> dict:
    return max(matches, key=lambda item: int(item.get("id", 0)))


#Confere se o municipio é o mesmo do arquivo CSV
def resolve_municipio(nome_input: str, index: Dict[str, List[dict]], keys: List[str]) -> dict:
    normalized = normalize_text(nome_input)

    if normalized in index:
        matches = index[normalized]
        chosen = pick_exact_match(matches)
        result = extract_fields(chosen)
        result["status"] = "OK"
        return result

    #Só aceita fuzzy match quando o candidato corresponde a um único município
    close = get_close_matches(normalized, keys, n=1, cutoff=0.90)
    if close:
        candidate_key = close[0]
        matches = index[candidate_key]
        if len(matches) == 1:
            result = extract_fields(matches[0])
            result["status"] = "OK"
            return result

    return {
        "municipio_ibge": "",
        "uf": "",
        "regiao": "",
        "id_ibge": "",
        "status": "NAO_ENCONTRADO",
    }

#Lê o arquivo CSV
def read_input_csv(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "municipio_input": row["municipio"],
                    "populacao_input": int(row["populacao"]),
                }
            )
    return rows

#Processa as linhas do arquivo CSV. Cria uma lista vazia e depois preenche
def process_rows(rows: List[dict], index: Dict[str, List[dict]], keys: List[str]) -> List[dict]:
    output = []
    for row in rows:
        try:
            resolved = resolve_municipio(row["municipio_input"], index, keys)
        except Exception:
            resolved = {
                "municipio_ibge": "",
                "uf": "",
                "regiao": "",
                "id_ibge": "",
                "status": "ERRO_API",
            }

        output.append(
            {
                "municipio_input": row["municipio_input"],
                "populacao_input": row["populacao_input"],
                "municipio_ibge": resolved["municipio_ibge"],
                "uf": resolved["uf"],
                "regiao": resolved["regiao"],
                "id_ibge": resolved["id_ibge"],
                "status": resolved["status"],
            }
        )
    return output

#Salva o resultado
def write_result_csv(rows: List[dict], path: Path) -> None:
    fieldnames = [
        "municipio_input",
        "populacao_input",
        "municipio_ibge",
        "uf",
        "regiao",
        "id_ibge",
        "status",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

#Calcula as estatísticas solicitadas, contando os resultados, linhas, não encontrados, falhas e etc.
def calculate_stats(rows: List[dict]) -> dict:
    total_municipios = len(rows)
    total_ok = sum(1 for row in rows if row["status"] == "OK")
    total_nao_encontrado = sum(1 for row in rows if row["status"] == "NAO_ENCONTRADO")
    total_erro_api = sum(1 for row in rows if row["status"] == "ERRO_API")
    pop_total_ok = sum(row["populacao_input"] for row in rows if row["status"] == "OK")

    region_values: Dict[str, List[int]] = defaultdict(list)
    for row in rows:
        if row["status"] == "OK" and row["regiao"]:
            region_values[row["regiao"]].append(row["populacao_input"])

    medias_por_regiao = {
        regiao: round(sum(values) / len(values), 2)
        for regiao, values in sorted(region_values.items())
    }

    return {
        "stats": {
            "total_municipios": total_municipios,
            "total_ok": total_ok,
            "total_nao_encontrado": total_nao_encontrado,
            "total_erro_api": total_erro_api,
            "pop_total_ok": pop_total_ok,
            "medias_por_regiao": medias_por_regiao,
        }
    }

#Salva o status
def write_stats_json(stats: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

#Envia os dados para a API
def submit_stats(access_token: str, stats_payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(CORRECAO_URL, headers=headers, json=stats_payload, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()

#Define os parâmetros aceitos pelo terminal
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Teste técnico Nasajon")
    parser.add_argument("--email", help="Email para login no Supabase")
    parser.add_argument("--password", help="Senha para login no Supabase")
    parser.add_argument("--access-token", help="Access token já obtido")
    parser.add_argument("--signup", action="store_true", help="Cria usuário no Supabase")
    parser.add_argument("--nome", help="Nome completo para signup")
    parser.add_argument("--skip-submit", action="store_true", help="Gera arquivos sem enviar correção")
    return parser.parse_args()

#Função main. Vai chamar as outras funções de acordo com a lógica necessária
def main() -> int:
    args = parse_args()

    try:
        if args.signup:
            if not args.email or not args.password or not args.nome:
                raise AppError("Para signup, informe --email, --password e --nome.")
            signup_response = signup(args.email, args.password, args.nome)
            print("Usuário criado com sucesso. Confirme o e-mail antes de fazer login.")
            print(json.dumps(signup_response, ensure_ascii=False, indent=2))
            return 0

        rows = read_input_csv(INPUT_CSV)

        try:
            municipios = fetch_ibge_municipios()
            index, keys = build_index(municipios)
            result_rows = process_rows(rows, index, keys)
        except requests.RequestException as exc:
            print(f"Falha ao consultar a API do IBGE: {exc}")
            result_rows = []
            for row in rows:
                result_rows.append(
                    {
                        "municipio_input": row["municipio_input"],
                        "populacao_input": row["populacao_input"],
                        "municipio_ibge": "",
                        "uf": "",
                        "regiao": "",
                        "id_ibge": "",
                        "status": "ERRO_API",
                    }
                )

        write_result_csv(result_rows, OUTPUT_CSV)
        stats_payload = calculate_stats(result_rows)
        write_stats_json(stats_payload, STATS_JSON)

        print("resultado.csv gerado com sucesso.")
        print(json.dumps(stats_payload, ensure_ascii=False, indent=2))

        if args.skip_submit:
            print("Envio para a API de correção foi pulado (--skip-submit).")
            return 0

        access_token = args.access_token
        if not access_token and args.email and args.password:
            access_token = login(args.email, args.password)

        if not access_token:
            print(
                "Nenhum ACCESS_TOKEN informado. Para enviar a correção, use --access-token ou --email/--password."
            )
            return 0

        correction_response = submit_stats(access_token, stats_payload)
        print("\nResposta da API de correção:")
        print(json.dumps(correction_response, ensure_ascii=False, indent=2))

        score = correction_response.get("score")
        if score is not None:
            print(f"\nScore final: {score}")

        return 0
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else ""
        print(f"Erro HTTP: {exc}\n{body}")
        return 1
    except AppError as exc:
        print(f"Erro: {exc}")
        return 1
    except Exception as exc:
        print(f"Erro inesperado: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
