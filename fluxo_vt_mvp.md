# Fluxo de compra de um vídeotape

## Cadastro
- o vt é cadastrado com status 'aguardando pagamento' por default da sua migration 
- É cadastrado uma entrada na timeline com o texto 'Pedido cadastrado no sistema'

## Pagamento e pendências
- Cada alteração no status do pagamento que o vt recebe é salva e cadastrada em sua timeline

### Quando o status de 'pagamento aprovado' é recebido pelo pagseguro acontece o seguinte: 
- é disparado um email avisando o cliente que o pagamento foi liberado

```
Recebemos a confirmação de seu pagamento. Muito obrigado. Daremos início imediato à produção de seu VT 
e o entregaremos rigorosamente no prazo acordado. Atenciosamente. Equipe VT Expresso.
```

- é chamado o metodo iniciarProducao() que ve se tem alguma pendencia como briefing e cliente ancine que deveriam ser preeenchidos apos o pagamento, caso tenha coloca o vt como pendente e manda a seguinte mensagem para o cliente:

```
Existem pendências ainda não preenchidas em seu pedido de VT que estão impedindo o início 
da produção de seu vídeo. Por favor, veja em seu painel (link) quais dados ainda precisamos. Atenciosamente. 
Equipe VT Expresso.
```

- O sistema fica aguardando até que o cliente providencie tudo que está faltando e a cada etapa ele roda denovo esse metodo para ver se ainda resta alguma pendencia, se restar ele reenvia a msg. Quando não tiver mais pendências o sistema prossegue enviando um email a todos os editores e fica disponivel para ser 'pego' por o primeiro editor disponivel

```
Tem um novo VT cartelado aguardando editor criativo e rápido. Mostre que você é rápido no gatilho.
Entre em seu Painel do Editor (link) e o pegue para você. No aguardo e na torcida. Equipe VT Expresso. 
```

## Mídias
- O editor entra em seu painel, vê um vt disponível e o pega para fazer, a partir de agora o vt so aparecerá para aquele editor.

### o editor pode recusar os materiais alegando que falta algo, acontece o seguite:
- o vt ganha status 'pendente'
- o item vt->checklist->midia_aprovada ganha 'reprovadas' indicando que esta faltando algo
- é cadastrado na timeline a mensagem do editor do porque ele recusou e o cliente é avisado por email com a msg

```
Os materias que você enviou para a produção do seu vídeo estão com alguma falha. Por favor, entre em seu painel (link), leia a a mensagem e corrija a pendência para que possamos continuar a edição do VT. O cronometro ficará parado até a resolução deste problema. Contando com sua compreensão, ficamos no aguardo. Atenciosamente. Equipe VT Expresso.
```

### o cliente le a msg do editor e manda um segundo pacote de midias atendendo a solicitação do editor e acontece o seguinte: 
- o vt volta pro status 'aguardando aprovação do material'
- o item vt->checklist->midia_aprovada volta para 'aguardando_aprovacao' para exibir no painel do editor que ele deve avaliar novamente os materiais recebidos
- é registrado na timeline a frase 'Foi enviado um novo pacote de materiais.' 
- o vt volta pro painel de produção do editor
- o editor é avisado por email com a msg

```
O cliente para o qual você solicitou mais materiais fez um novo upload. Por favor, entre no sistema e continue a edição. O cronômetro voltou a correr. Equipe VT Expresso.
```

### o editor aprovando o material enviado aconteceu o seguinte: 
- o vt recebe status 'em_produção' 
- o item vt->checklist->midia_aprovada recebe 'aprovada' para indicar que aqueles materiais enviados estão ok
- o vt inicia seu cronometro regressivo e é registrado na timeline a frase 'O editor aprovou os materiais e deu início a produção do VT'
- o vt fica aguardando o editor fazer seu trabalho e é enviado um email para o cliente com a msg

```
Está tudo certo com os materias que você enviou para a produção de seu vídeo no VT Expresso. Fique tranquilo. A produção já foi iniciada e você receberá o seu vídeo no prazo combinado. O cronômetro voltou a correr. Equipe VT Expresso.  
```

## Inicio da produção
- o vt agora aparece 'em produção' para cliente e editor com cronometro sendo mostrado para os dois e o editor deve ter a opçao de pausar e retomar o cronometro ++++++ O EDITOR NAO PODE TER ESTA OPÇÃO (senão, ele pode pausar para ir ao banheiro ou fazer um lanche). NA REALIDADE, SÓ QUANDO ELE NÃO APROVAR ALGO DO CLIENTE, O CRONOMETRO DEVE SER PAUSADO AUTOMATICAMENTE, E RETOMADO QDO ELE APROVAR. MESMO SE ELE NÃO APROVAR O AUDIO DO EDITOR, O CRONOMETRO NAO PARA +++++

quando o vt é pausado ele ganha status 'pendente' e vai para a aba pendentes do cliente com um aviso dizendo 'teve sua produção pausada pelo editor, POR ARQUIVOS DO CLIENTE COM O(S) PROBLEMA(S)   __________ (apontar a causa que editor escrever)', na timeline é registrada a frase 'O cronômetro teve sua contagem pausada'

quando é retomado ele volta para 'em producao' e na timeline é registrada a frase 'O cronômetro teve sua contagem retomada'

- o editor faz todo o trabalho nessa versão mvp, envia para locutor e roteirista se for necessario, pega o resultado do trabalho deles faz o seu e manda o revisor aprovar, estando aprovado coloca no painel e vai para aprovação do cliente e acontece: 
- é registrado na timeline 'o editor enviou o vudei para avaliação do cliente'
- o vt recebe status 'aguardando_aprovacao_cliente' 
- o vt vai para a parte de finalizados do cliente onde ele tera a opção de pedir alterações
- é enviado para o cliente o email

```
O seu vídeo foi concluído, dentro do prazo estipulado. Por favor,  entre em seu painel (link) para revisá-lo e aprová-lo ou, se for o caso, solicitar revisão. Para revisão, use o formulário do VT Expresso. É importante que você coloque neste formulário tudo o que gostaria de ver alterado. Você tem direito a duas revisões de vídeo gratuitamente, desde que não incluia mudanças no roteiro aprovado. Para mudança no scrip do locutor, é necessária nova locução _ o que tem um custo adicional de 15%. No aguardo e na torcida. Equipe VT Expresso
```

### caso o cliente reprove o vt ele deve preencher um form de alteração de vt, acontece:
- o vt volta pro status 'em REVISÃO'
- é registrado na timeline 'Foram solicitadas alterações no VT pelo cliente'
- é enviado um aviso ao editor por email

```
O cliente solicitou alterações no VT {id_do_vt}. Por favor, entre no Paiel do Editor e faça as revisões necessárias. Você tem 3 horas para concluir as alterações e subir o link do vídeo Revisado no VT Expresso. No aguardo e na torcida. VT Expresso
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
Parabéns, o cliente aprovou o VT [id_do_vt]. Excelente trabalhol. Por favor, exporte-o em alta definição em MOV e em MP4, faça o upload no seu Google Drive do VT Expresso. Você tem 1 hora pra isso. Muito obrigado por estar vestindo a camisa do VT Expresso.
```
