# Fluxo de compra de um vídeotape

## Cadastro
- o vt é cadastrado com status 'aguardando pagamento' por default da sua migration 
- É cadastrado uma entrada na timeline com o texto 'Pedido cadastrado no sistema'

## Pagamento e pendências
- Cada alteração no status do pagamento que o vt recebe é salva e cadastrada em sua timeline

### Quando o status de 'pagamento aprovado' é recebido pelo pagseguro acontece o seguinte: 
- é disparado um email avisando o cliente que o pagamento foi liberado

```
Recebemos a confirmação de seu pagamento. Obrigado.
```

- é chamado o metodo iniciarProducao() que ve se tem alguma pendencia como briefing e cliente ancine que deveriam ser preeenchidos apos o pagamento, caso tenha coloca o vt como pendente e manda a seguinte mensagem para o cliente:

```
Existem pendências ainda não preenchidas no seu vt impedindo que possamos dar início na produção, por favor veja em seu painel quais dados precisamos.
```

- O sistema fica aguardando até que o cliente providencie tudo que está faltando e a cada etapa ele roda denovo esse metodo para ver se ainda resta alguma pendencia, se restar ele reenvia a msg. Quando não tiver mais pendências o sistema prossegue enviando um email a todos os editores e fica disponivel para ser 'pego' por o primeiro editor disponivel

```
Tem um novo vt com pagamento liberado aguardando por um editor no seu painel de editor
```

## Mídias
- O editor entra em seu painel, vê um vt disponível e o pega para fazer, a partir de agora o vt so aparecerá para aquele editor.

### o editor pode recusar os materiais alegando que falta algo, acontece o seguite:
- o vt ganha status 'pendente'
- o item vt->checklist->midia_aprovada ganha 'reprovadas' indicando que esta faltando algo
- é cadastrado na timeline a mensagem do editor do porque ele recusou e o cliente é avisado por email com a msg

```
Os materias que você enviou para a produção do vt vieram com algumas pendências, por favor pedimos para que revise em seu painel
```

### o cliente le a msg do editor e manda um segundo pacote de midias atendendo a solicitação do editor e acontece o seguinte: 
- o vt volta pro status 'aguardando aprovação do material'
- o item vt->checklist->midia_aprovada volta para 'aguardando_aprovacao' para exibir no painel do editor que ele deve avaliar novamente os materiais recebidos
- é registrado na timeline a frase 'Foi enviado um novo pacote de materiais.' 
- o vt volta pro painel de produção do editor
- o editor é avisado por email com a msg

```
Um cliente para o qual você solicitou mais materiais fez um novo upload.
```

### o editor aprovando o material enviado aconteceu o seguinte: 
- o vt recebe status 'em_produção' 
- o item vt->checklist->midia_aprovada recebe 'aprovada' para indicar que aqueles materiais enviados estão ok
- o vt inicia seu cronometro regressivo e é registrado na timeline a frase 'O editor aprovou os materiais e deu início a produção do vídeotape'
- o vt fica aguardando o editor fazer seu trabalhoe é enviado um email para o cliente com a msg

```
Os materias que vc enviou para a produção do vt foram aceitos pelo editor e a produção foi iniciada
```

## Inicio da produção
- o vt agora aparece 'em produção' para cliente e editor com cronometro sendo mostrado para os dois e o editor deve ter a opçao de pausar e retomar o cronometro

quando o vt é pausado ele ganha status 'pendente' e vai para a aba pendentes do cliente com um aviso dizendo 'teve sua produção pausada pelo editor', na timeline é registrada a frase 'O cronômetro teve sua contagem pausada'

quando é retomado ele volta para 'em producao' e na timeline é registrada a frase 'O cronômetro teve sua contagem retomada'

- o editor faz todo o trabalho nessa versão mvp, envia para locutor e roteirista se for necessario, pega o resultado do trabalho deles faz o seu e manda o revisor aprovar, estando aprovado coloca no painel e vai para aprovação do cliente e acontece: 
- é registrado na timeline 'o editor enviou o videotape para avaliação do cliente'
- o vt recebe status 'aguardando_aprovacao_cliente' 
- o vt vai para a parte de finalizados do cliente onde ele tera a opção de pedir alterações
- é enviado para o cliente o email

```
O seu vídeotape foi concluído, por favor entre em seu painel para avaliá-lo
```

### caso o cliente reprove o vt ele deve preencher um form de alteração de vt, acontece:
- o vt volta pro status 'em produção'
- é registrado na timeline 'Foram solicitadas alterações no vídeotape pelo cliente'
- é enviado um aviso ao editor por email

```
O cliente solicitou alterações para o vídeotape {id_do_vt}'
```

o editor visualiza o form de alteração, faz as alterações necessarias e reenvia o vt
para o cliente e o cliclo se repete

o fluxo de alterações com form de alterações de vt se repete ate o cliente 
aprovar e o vt ganhar status de concluido

### Quando o cliente aprova o vt acontece o seguinte:
- o vt ganhar status de 'concluido' e vai para a aba finalizados do editor e do cliente
- é salvo na timeline a frase 'O cliente aprovou o vídeotape'
- o editor recebe um email com a msg

```
Parabéns, o cliente aprovou o vídeotape [id_do_vt]
```