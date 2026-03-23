# Notas explicativas

## Decisões principais

1. A solução baixa todos os municípios de uma vez pela API de localidades do IBGE e monta um índice em memória.
2. O matching é feito em duas etapas:
   - match exato após normalização (remoção de acentos, case-insensitive, espaços extras e pontuação);
   - match aproximado com `difflib.get_close_matches`, para corrigir entradas com erros como `Belo Horzionte`, `Curitba` e `Santoo Andre`.
3. O CSV de saída preserva exatamente o nome de entrada em `municipio_input` e a população original em `populacao_input`.
4. As estatísticas consideram apenas linhas com status `OK`, como exigido.
5. O envio da correção usa autenticação no Supabase. O programa aceita:
   - e-mail + senha, fazendo login automaticamente;
   - ou um `ACCESS_TOKEN` já obtido.
6. O código trata falhas de rede e resposta inválida da API, marcando `ERRO_API` quando necessário.

## Observações

- Como o teste exige confirmação de e-mail, essa etapa não pode ser automatizada sem acesso à caixa postal do candidato.
- O arquivo `resultado.csv` incluído aqui já está preenchido com o resultado esperado para o `input.csv` fornecido.
