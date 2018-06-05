/**
* Recebe um float ou int e tranforma em uma string monetária ex.: R$ 1.000,99
*/
function numberToReal(numero) {
    var numero = numero.toFixed(2).split('.');
    numero[0] = "R$ " + numero[0].split(/(?=(?:...)*$)/).join('.');
    return numero.join(',');
}

function isFloat(n){
	return n === +n && n !== (n|0);
}

function isInteger(n){
	return n === +n && n === (n|0);
}

//mascara e desmascara um float como real brasileiro
<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery-maskmoney/3.0.2/jquery.maskMoney.min.js" type="text/javascript"></script>

function mascarar(id){
	$(".real").maskMoney({
		prefix: "R$ ",
		decimal: ",",
		thousands: "."
	});
	$(id).maskMoney('mask');
}

function desmascarar(string){
	var num = parseFloat(string.replace('R$ ', '').replace('.', '').replace(',', '.'));
	return num;
}

