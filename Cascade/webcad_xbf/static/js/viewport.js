console.log("🌌 Viewport Engine Initializing...");

let scene, camera, renderer, controls;

function initViewport() {
    const container = document.getElementById('viewport-container');
    if (!container) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x3f3f46);

    const aspect = container.clientWidth / container.clientHeight;
    camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
    camera.position.set(50, 50, 50);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.insertBefore(renderer.domElement, container.firstChild);

    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(10, 20, 10);
    scene.add(dirLight);

    const gridHelper = new THREE.GridHelper(100, 100, 0x555555, 0x444444);
    scene.add(gridHelper);
    
    const axesHelper = new THREE.AxesHelper(10);
    scene.add(axesHelper);

    window.addEventListener('resize', onWindowResize, false);
    animate();
    console.log("✅ Viewport Engine Ready.");
}

function onWindowResize() {
    const container = document.getElementById('viewport-container');
    if (!container || !renderer || !camera) return;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}

function animate() {
    requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) renderer.render(scene, camera);
}

document.addEventListener('DOMContentLoaded', initViewport);
