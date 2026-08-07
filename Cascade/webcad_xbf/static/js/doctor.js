// CascadeCAD Doctor of Truth
// Frontend controller

console.log("CascadeCAD Doctor loaded");

async function loadDoctorRepository() {
    try {
        const response = await fetch("/api/doctor/repository");

        if (!response.ok) {
            throw new Error("Doctor API unavailable");
        }

        const data = await response.json();

        document.getElementById("js-count").textContent =
            data.javascript ?? "--";

        document.getElementById("py-count").textContent =
            data.python ?? "--";

        document.getElementById("html-count").textContent =
            data.html ?? "--";

        document.getElementById("status").textContent =
            "Repository scan complete";

    } catch (error) {

        console.error("Doctor error:", error);

        document.getElementById("status").textContent =
            "Doctor backend not connected yet";

    }
}


document.addEventListener("DOMContentLoaded", () => {
    loadDoctorRepository();
});
