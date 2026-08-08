import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export class Viewport {
    constructor(app) {
        this.app = app;
        this.canvas = document.getElementById('three-canvas');
        this.container = document.getElementById('viewport-container');
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
        this.renderer = new THREE.WebGLRenderer({ 
            canvas: this.canvas, 
            antialias: true,
            powerPreference: "high-performance"
        });
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.raycaster = new THREE.Raycaster();
        this.pointer = new THREE.Vector2();
        this.objects = new Map(); // Map from part ID to THREE.Mesh
        this.lastFrameTime = 0;
        this.fpsCounter = document.getElementById('status-fps');
    }

    initialize() {
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.scene.background = new THREE.Color(0x121418);

        // Lights
        this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.0);
        dirLight1.position.set(1, 1, 1);
        this.scene.add(dirLight1);
        const dirLight2 = new THREE.DirectionalLight(0x8888ff, 0.5);
        dirLight2.position.set(-1, -1, -0.5);
        this.scene.add(dirLight2);

        // Ground Grid
        const grid = new THREE.GridHelper(200, 20, 0x444444, 0x444444);
        grid.material.opacity = 0.2;
        grid.material.transparent = true;
        this.scene.add(grid);

        // Controls
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.1;
        this.camera.position.set(100, 100, 100);
        this.controls.update();

        // View Cube
        this.initViewCube();

        // Event Listeners
        window.addEventListener('resize', () => this.onResize());
        this.container.addEventListener('pointerdown', (e) => this.onPointerDown(e));

        this.animate(0);
        this.app.Telemetry.log('VIEW', 'Viewport initialized');
    }

    animate(time) {
        requestAnimationFrame((t) => this.animate(t));
        this.controls.update();
        
        // Update view cube orientation
        if (this.viewCube) {
            this.viewCube.quaternion.copy(this.camera.quaternion).invert();
        }

        this.renderer.render(this.scene, this.camera);
        
        // FPS Counter
        const delta = time - this.lastFrameTime;
        this.lastFrameTime = time;
        if (delta > 0) {
            const fps = 1000 / delta;
            this.fpsCounter.textContent = `FPS: ${Math.round(fps)}`;
        }
    }

    onResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.app.Telemetry.log('VIEW', 'Viewport resized', { w: this.container.clientWidth, h: this.container.clientHeight });
    }

    onPointerDown(event) {
        if (event.target !== this.canvas) return; // Ignore clicks on UI elements over the canvas

        this.pointer.x = (event.clientX / this.container.clientWidth) * 2 - 1;
        this.pointer.y = -(event.clientY / this.container.clientHeight) * 2 + 1;

        this.raycaster.setFromCamera(this.pointer, this.camera);
        const intersects = this.raycaster.intersectObjects(Array.from(this.objects.values()));

        if (intersects.length > 0) {
            const partId = intersects[0].object.userData.partId;
            const selection = new Set(this.app.State.get('selection'));
            
            if (event.ctrlKey || event.metaKey) {
                selection.has(partId) ? selection.delete(partId) : selection.add(partId);
            } else {
                selection.clear();
                selection.add(partId);
            }
            this.app.State.set('selection', selection);
        } else {
            // Clicked on empty space
            if (!event.ctrlKey && !event.metaKey) {
                this.app.State.set('selection', new Set());
            }
        }
    }

    clearScene() {
        this.objects.forEach(mesh => {
            this.scene.remove(mesh);
            mesh.geometry.dispose();
            if (Array.isArray(mesh.material)) {
                mesh.material.forEach(m => m.dispose());
            } else {
                mesh.material.dispose();
            }
        });
        this.objects.clear();
        this.app.State.set('triangleCount', 0);
        this.app.Telemetry.log('VIEW', 'Scene cleared');
    }

    loadMeshes(meshBuffers) {
        this.clearScene();
        let totalTriangles = 0;

        meshBuffers.forEach(meshData => {
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(meshData.positions, 3));
            if (meshData.normals && meshData.normals.length > 0) {
                geometry.setAttribute('normal', new THREE.Float32BufferAttribute(meshData.normals, 3));
            }
            if (meshData.indices && meshData.indices.length > 0) {
                geometry.setIndex(meshData.indices);
            }
            
            if (!geometry.attributes.normal) {
                geometry.computeVertexNormals();
            }

            const material = new THREE.MeshStandardMaterial({
                color: new THREE.Color(...(meshData.color || [0.8, 0.8, 0.8])),
                metalness: 0.3,
                roughness: 0.6,
                transparent: (meshData.opacity || 1.0) < 1.0,
                opacity: meshData.opacity || 1.0,
            });

            const mesh = new THREE.Mesh(geometry, material);
            mesh.name = meshData.name;
            mesh.userData.partId = meshData.uuid;
            
            this.scene.add(mesh);
            this.objects.set(meshData.uuid, mesh);
            totalTriangles += (geometry.index ? geometry.index.count : geometry.attributes.position.count) / 3;
        });
        
        this.app.State.set('triangleCount', Math.round(totalTriangles));
        this.app.Telemetry.log('MESH', 'Meshes loaded', { count: meshBuffers.length, triangles: Math.round(totalTriangles) });
        this.fitToView();
    }

    updateSelectionHighlight(selectionSet) {
        this.objects.forEach((mesh, partId) => {
            const isSelected = selectionSet.has(partId);
            // A more robust implementation would use an outline pass or a second material
            mesh.material.emissive.setHex(isSelected ? 0x61afef : 0x000000);
        });
    }

    fitToView() {
        const box = new THREE.Box3();
        if (this.objects.size === 0) {
            this.controls.target.set(0, 0, 0);
            this.camera.position.set(100, 100, 100);
            this.controls.update();
            return;
        }

        this.objects.forEach(mesh => box.expandByObject(mesh));

        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxSize = Math.max(size.x, size.y, size.z);
        const fitHeightDistance = maxSize / (2 * Math.atan(Math.PI * this.camera.fov / 360));
        const fitWidthDistance = fitHeightDistance / this.camera.aspect;
        const distance = 1.5 * Math.max(fitHeightDistance, fitWidthDistance);

        const direction = this.camera.position.clone().sub(this.controls.target).normalize();
        
        this.controls.target.copy(center);
        this.camera.position.copy(center).add(direction.multiplyScalar(distance));
        this.camera.near = distance / 100;
        this.camera.far = distance * 100;
        this.camera.updateProjectionMatrix();

        this.controls.update();
        this.app.Telemetry.log('VIEW', 'Fit to view executed');
    }

    // --- View Cube ---
    initViewCube() {
        const cubeContainer = document.getElementById('view-cube-container');
        this.viewCube = new THREE.Object3D();
        cubeContainer.appendChild(this.renderer.domElement); // This is a trick; we render it separately.
        
        const loader = new THREE.TextureLoader();
        const faceMaterial = (text) => new THREE.MeshBasicMaterial({
            color: 0xcccccc,
            alphaMap: loader.load(this.createTextTexture(text)),
            alphaTest: 0.5,
            side: THREE.DoubleSide
        });

        const cubeGeo = new THREE.BoxGeometry(1, 1, 1);
        const materials = [
            faceMaterial('RIGHT'), faceMaterial('LEFT'),
            faceMaterial('TOP'), faceMaterial('BOTTOM'),
            faceMaterial('FRONT'), faceMaterial('BACK')
        ];
        const cube = new THREE.Mesh(cubeGeo, materials);
        
        const edges = new THREE.EdgesGeometry(cubeGeo);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x888888 }));
        
        this.viewCube.add(cube);
        this.viewCube.add(line);
        
        // This is a simplified approach. A real implementation uses a separate scene and renderer.
        // For now, we'll just handle clicks on the HTML elements and orient the camera.
        const cubeHtml = `
            <div id="view-cube">
                <div class="view-cube-face face-front" data-direction="0,0,1">FRONT</div>
                <div class="view-cube-face face-back" data-direction="0,0,-1">BACK</div>
                <div class="view-cube-face face-right" data-direction="1,0,0">RIGHT</div>
                <div class="view-cube-face face-left" data-direction="-1,0,0">LEFT</div>
                <div class="view-cube-face face-top" data-direction="0,1,0">TOP</div>
                <div class="view-cube-face face-bottom" data-direction="0,-1,0">BOTTOM</div>
            </div>
        `;
        cubeContainer.innerHTML = cubeHtml;
        cubeContainer.addEventListener('click', (e) => {
            const face = e.target.closest('[data-direction]');
            if (face) {
                const dir = face.dataset.direction.split(',').map(Number);
                this.setCameraDirection(new THREE.Vector3(...dir));
            }
        });
    }

    setCameraDirection(direction) {
        const distance = this.camera.position.distanceTo(this.controls.target);
        const newPos = this.controls.target.clone().add(direction.multiplyScalar(distance));
        
        // A tweening library like TWEEN.js would make this smooth
        this.camera.position.copy(newPos);
        this.controls.update();
    }

    createTextTexture(text) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 128;
        canvas.height = 128;
        context.fillStyle = 'rgba(0,0,0,0)'; // Transparent background
        context.fillRect(0, 0, 128, 128);
        context.fillStyle = 'white';
        context.font = 'bold 20px sans-serif';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(text, 64, 64);
        return canvas.toDataURL();
    }
}