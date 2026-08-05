const page = document.body.dataset;
const basePath = String(page.basePath || '').replace(/\/$/, '');

function appPath(path = '/') {
    const normalized = path.startsWith('/') ? path : `/${path}`;
    return `${basePath}${normalized}`;
}


window.CascadeImport = {

async start(file) {

const stage = document.getElementById("import-stage");

try {

stage.textContent = "Creating upload...";


const started = await fetch(
    appPath("/api/uploads/start"),
    {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            filename: file.name,
            size: file.size,
            project_name: "Imported CAD Model"
        })
    }
).then(r => r.json());


if (started.error) {
    throw new Error(started.error);
}


const chunkSize = Number(started.chunk_bytes);

let offset = Number(started.upload.received || 0);


while (offset < file.size) {

    const chunk = file.slice(
        offset,
        offset + chunkSize
    );


    const result = await fetch(
        appPath(
          `/api/uploads/${started.upload.id}/chunk?offset=${offset}`
        ),
        {
            method: "PUT",
            body: chunk
        }
    ).then(r => r.json());


    if (result.error) {
        throw new Error(result.error);
    }


    offset = Number(result.received);


    stage.textContent =
        `Uploading ${Math.floor(offset / file.size * 100)}%`;


    window.CascadeImportProgress?.run();

}



stage.textContent =
    "Queueing geometry import...";


const finished = await fetch(
    appPath(`/api/uploads/${started.upload.id}/finish`),
    {
        method:"POST"
    }
).then(r => r.json());


if (finished.error) {
    throw new Error(finished.error);
}


stage.textContent =
    "Import complete";


window.location.assign(
    appPath(`/project/${finished.project_id}`)
);


}

catch(error) {

console.error(
    "CAD import failed:",
    error
);

stage.textContent =
    "Import failed: " + error.message;

}

}

};
