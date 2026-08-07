console.log("🌌 CascadeCAD Viewport Initializing...");

import * as THREE from "/static/vendor/three/three.module.js";
import { OrbitControls } from "/static/vendor/three/OrbitControls.js";
import { GLTFLoader } from "/static/vendor/three/GLTFLoader.js";

let scene;
let camera;
let renderer;
let controls;
let model;

function getProjectId() {
    const parts = window.location.pathname.split("/");
    const index = parts.indexOf("project");

    if (index !== -1 && parts[index + 1]) {
        return parts[index + 1];
    }

    return document.body.dataset.projectId || null;
}

function initViewport() {

    const container =
        document.getElementById("viewer") ||
        document.getElementById("viewport-container");

    if (!container) {
        console.error("❌ Viewer container not found");
        return;
    }

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x181c22);

    camera = new THREE.PerspectiveCamera(
        45,
        container.clientWidth / container.clientHeight,
        0.1,
        5000
    );

    camera.position.set(50, 50, 50);

    renderer = new THREE.WebGLRenderer({
        antialias: true
    });

    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(
        container.clientWidth,
        container.clientHeight
    );

    container.appendChild(renderer.domElement);

    controls = new OrbitControls(
        camera,
        renderer.domElement
    );

    controls.enableDamping = true;

    scene.add(
        new THREE.AmbientLight(
            0xffffff,
            0.7
        )
    );

    const light = new THREE.DirectionalLight(
        0xffffff,
        1.0
    );

    light.position.set(20, 40, 20);
    scene.add(light);


    const grid = new THREE.GridHelper(
        200,
        200
    );

    scene.add(grid);


    window.addEventListener(
        "resize",
        resizeViewport
    );


    const projectId = getProjectId();

    if (projectId) {
        loadGLB(projectId);
    }
    else {
        console.warn(
            "No project id detected"
        );
    }


    animate();

    console.log(
        "✅ CascadeCAD Viewport Ready"
    );
}


function loadGLB(projectId) {

    const url =
        `/api/render/${projectId}`;

    console.log(
        "📡 Loading GLB:",
        url
    );


    const loader = new GLTFLoader();


    loader.load(
        url,

        function(gltf) {

            model = gltf.scene;

            scene.add(model);

            fitModel();

            console.log(
                "✅ GLB loaded"
            );

        },

        function(progress) {

            if (progress.total) {
                console.log(
                    "Loading:",
                    Math.round(
                        progress.loaded /
                        progress.total * 100
                    ),
                    "%"
                );
            }

        },

        function(error) {

            console.error(
                "❌ GLB load failed",
                error
            );

        }
    );
}


function fitModel() {

    if (!model) return;


    const box =
        new THREE.Box3()
        .setFromObject(model);


    const center =
        box.getCenter(
            new THREE.Vector3()
        );


    const size =
        box.getSize(
            new THREE.Vector3()
        );


    const max =
        Math.max(
            size.x,
            size.y,
            size.z
        );


    camera.position.set(
        center.x + max,
        center.y + max,
        center.z + max
    );


    controls.target.copy(center);
    controls.update();
}


function resizeViewport() {

    const container =
        document.getElementById("viewer");

    if (!container) return;

    camera.aspect =
        container.clientWidth /
        container.clientHeight;

    camera.updateProjectionMatrix();

    renderer.setSize(
        container.clientWidth,
        container.clientHeight
    );
}


function animate() {

    requestAnimationFrame(
        animate
    );

    if (controls) {
        controls.update();
    }

    if (
        renderer &&
        scene &&
        camera
    ) {
        renderer.render(
            scene,
            camera
        );
    }
}


document.addEventListener(
    "DOMContentLoaded",
    initViewport
);
