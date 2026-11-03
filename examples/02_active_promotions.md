# Active Promotions

## Scenario
Promotion lookup and discount information.

## Environment
- Interface: Python CLI
- LLM provider: Ollama (local)
- Language: Brazilian Portuguese
- Data source: provided CSV files and store policy PDF

## Conversation

### Customer
Oi! Quais instrumentos estão em promoção?

### Assistant
Oi! Atualmente temos as seguintes ofertas para instrumentos:

1. Kalani KAL-700T Tenor Natural: 10% de desconto (R$359,00 → R$323,10), 11 unidades disponíveis.  
2. Ohana CK-20 Concert Natural: 20% de desconto (R$549,00 → R$439,20), 6 unidades disponíveis.  
3. Crafter HT-100 Folk Aço Natural: 18% de desconto (R$2.399,00 → R$1.967,18), 3 unidades disponíveis.  
4. Taylor 110e Dreadnought Natural: 8% de desconto (R$5.999,00 → R$5.519,08), 4 unidades disponíveis.  

Observação: Não há desconto adicional via PIX para essas ofertas.

### Tools Executed
- `get_active_promotions`

### Customer
Gostei do ukulele Ohana CK-20. Quanto ele está custando com o desconto?

### Assistant
O Ohana CK-20 Concert Natural está com desconto de 20% no preço original (R$549,00), totalizando R$439,20. 😊  
Temos 6 unidades disponíveis para você!

### Tools Executed
- None

### Customer
Se eu pagar no PIX, consigo mais 5% de desconto?

### Assistant
O desconto de 5% no PIX não é cumulativo com promoções. Segundo as políticas da Empório da Música, o desconto de PIX (5%) só se aplica ao preço de tabela regular do produto, não a preços já promocionais. Portanto, se você adquirir um item com promoção (como Black Friday ou Aniversário da Loja), o desconto de 5% no PIX não será aplicado. 

Para confirmar: 
- Promoções (ex.: 15% de desconto em Black Friday) já reduzem o preço do produto. 
- O desconto de 5% no PIX só é válido para o preço original do produto (não para preços já promocionais).

Se precisar de mais esclarecimentos, estou aqui para ajudar! 😊

### Tools Executed
- `search_policies`

## Notes
- Transcript captured from an actual local execution.
- Tool names were recorded from the agent conversation.
- Email addresses were redacted for publication.
- Tool arguments and raw results were not exported.
- Accuracy should be reviewed before submission.
