/*
 CascadeCAD Engineering Diagnostic Console
*/

window.CADLog = {

    symbols: {
        system: "Σ",
        command: "λ",
        geometry: "Γ",
        transform: "Δ",
        mesh: "△",
        math: "√",
        stream: "∞",
        complete: "Ω",
        warning: "⚠",
        error: "✖"
    },

    write(type, message) {

        const symbol =
            this.symbols[type] || "•";

        console.log(
            `${symbol} ${message}`
        );
    }
};


console.log(
    "Σ CascadeCAD Diagnostic Layer Online"
);

