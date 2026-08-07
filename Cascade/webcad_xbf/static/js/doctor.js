console.log("CascadeCAD Doctor loaded");

async function loadDoctorAPI() {

    const response = await fetch("/api/doctor/api");
    const data = await response.json();

    document.getElementById("api-count").textContent =
        data.count;

    document.getElementById("api-status").textContent =
        "PASS";
}




async function loadDoctorRepository() {

    try {

        const response = await fetch("/api/doctor/repository");

        if (!response.ok) {
            throw new Error("Doctor API unavailable");
        }

        const data = await response.json();


        document.getElementById("js-count").textContent =
            data.javascript;

        document.getElementById("py-count").textContent =
            data.python;

        document.getElementById("html-count").textContent =
            data.html;


        document.getElementById("status-message").textContent =
            "Doctor scan complete";


    } catch (error) {

        console.error(error);

        document.getElementById("status-message").textContent =
            "Doctor connection failed";

    }
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        loadDoctorRepository();
        loadDoctorAPI();
    }
);



document.addEventListener(
    "DOMContentLoaded",
    loadDoctorRepository
);
