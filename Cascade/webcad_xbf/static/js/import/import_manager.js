window.CascadeImport = {

start(file) {

console.log(
"CascadeCAD import:",
file.name
);


document.getElementById(
"import-stage"
).textContent =
"Reading " + file.name;


window.CascadeImportProgress?.run();

}

};
