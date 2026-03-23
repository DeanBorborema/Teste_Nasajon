# Teste técnico Nasajon - solução em Python

## Como rodar

Primeiro, é necessário ter os requests:
" pip install requests "

Após isso criar a conta:
" python app.py --signup --email "SEU_EMAIL" --password "SUA_SENHA" --nome "Seu Nome Completo" "

Confirmar o email e, após a confirmação, enviar:
" python app.py --email "SEU_EMAIL" --password "SUA_SENHA" "

Também é possível passar um token já obtido:

" python app.py --access-token "SEU_ACCESS_TOKEN" "

## Arquivos

- `input.csv`: arquivo de entrada exigido pelo teste
- `resultado.csv`: saída gerada
- `stats.json`: estatísticas no formato pedido
- `app.py`: solução completa
- `notas_explicativas.md`: decisões técnicas
