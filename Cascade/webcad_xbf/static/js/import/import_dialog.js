window.CascadeImportDialog = {

init() {

const button =
document.getElementById("import-model-btn");

const dialog =
document.getElementById("import-dialog");

if (!button || !dialog)
return;


button.onclick = () =>
dialog.showModal();


document.getElementById("start-import")
?.addEventListener("click", () => {

const file =
document.getElementById("cad-import-file")
.files[0];


if (!file) {

alert("Select a CAD file first.");
return;

}

window.CascadeImport.start(file);

});

}

};


document.addEventListener(
"DOMContentLoaded",
() => window.CascadeImportDialog.init()
);
