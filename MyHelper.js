/**
* Recebe um float ou int e tranforma em uma string monetária ex.: R$ 1.000,99
*/
function numberToReal(numero) {
    var numero = numero.toFixed(2).split('.');
    numero[0] = "R$ " + numero[0].split(/(?=(?:...)*$)/).join('.');
    return numero.join(',');
}
