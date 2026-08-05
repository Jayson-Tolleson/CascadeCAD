window.CascadeImportProgress = {

run() {

const stages = [
"Reading file",
"Parsing geometry",
"Healing topology",
"Building scene",
"Ready"
];


let i = 0;


const timer =
setInterval(() => {

const el =
document.getElementById(
"import-stage"
);


if (el)
el.textContent =
stages[i];


i++;


if (i >= stages.length)
clearInterval(timer);


},700);

}

};
