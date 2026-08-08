import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Telemetry } from './telemetry.js';
import { State } from './state.js';

export class Viewport {
    constructor(canvas, container) {
        this.canvas = canvas;
        this.container = container;
        
        this.initRenderer();
        this.initScene();
        this.initCamera();
        this.initControls();
        this.initLights();
        this.initHelpers();

        window.addEventListener('resize', this.onResize.bind(this), false);
        
        this.animate();
        Telemetry.log('VIEW', 'Viewport initialized');
    }

    initRenderer() {
        this.renderer = new THREE.WebGLRenderer({ 
            canvas: this.canvas, 
            antialias: true,
            powerPreference: "high-performance"
        });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
    }

    initScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x282c34);
    }

    initCamera() {
        this.camera = new THREE.PerspectiveCamera(50, this.container.clientWidth / this.container.clientHeight, 0.1, 2000);
        this.camera.position.set(50, 50, 50);
    }

    initControls() {
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.1;
    }

    initLights() {
        const ambient = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambient);

        const keyLight = new THREE.DirectionalLight(0xffffff, 0.8);
        keyLight.position.set(100, 100, 100);
        this.scene.add(keyLight);

        const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
        fillLight.position.set(-100, 50, -100);
        this.scene.add(fillLight);
    }

    initHelpers() {
        const gridHelper = new THREE.GridHelper(100, 10);
        this.scene.add(gridHelper);
        const axesHelper = new THREE.AxesHelper(10);
        this.scene.add(axesHelper);
    }

    onResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        Telemetry.log('VIEW', 'Viewport resized', { w: this.container.clientWidth, h: this.container.clientHeight });
    }

    animate() {
        requestAnimationFrame(this.animate.bind(this));
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    clearScene() {
        const meshes = this.scene.children.filter(c => c.isMesh);
        meshes.forEach(mesh => {
            this.scene.remove(mesh);
            mesh.geometry.dispose();
            mesh.material.dispose();
        });
        State.set('triangleCount', 0);
        Telemetry.log('VIEW', 'Scene cleared');
    }

    loadMeshes(meshBuffers) {
        this.clearScene();
        let totalTriangles = 0;

        meshBuffers.forEach(meshData => {
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(meshData.positions, 3));
            if (meshData.normals) {
                geometry.setAttribute('normal', new THREE.Float32BufferAttribute(meshData.normals, 3));
            }
            if (meshData.indices) {
                geometry.setIndex(meshData.indices);
            }
            
            if (!meshData.normals) {
                geometry.computeVertexNormals();
            }

            const material = new THREE.MeshStandardMaterial({ 
                color: Math.random() * 0xffffff,
                metalness: 0.5,
                roughness: 0.5
            });

            const mesh = new THREE.Mesh(geometry, material);
            mesh.name = meshData.uuid;
            this.scene.add(mesh);
            totalTriangles += (geometry.index ? geometry.index.count : geometry.attributes.position.count) / 3;
        });
        
        State.set('triangleCount', Math.round(totalTriangles));
        Telemetry.log('MESH', 'Meshes loaded', { count: meshBuffers.length, triangles: Math.round(totalTriangles) });
        this.fitToView();
    }

    fitToView() {
        const box = new THREE.Box3();
        const meshes = this.scene.children.filter(c => c.isMesh);
        if (meshes.length === 0) {
            this.controls.target.set(0,0,0);
            this.camera.position.set(50,50,50);
            this.camera.lookAt(0,0,0);
            this.controls.update();
            return;
        }

        meshes.forEach(mesh => box.expandByObject(mesh));

        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxSize = Math.max(size.x, size.y, size.z);
        const fitHeightDistance = maxSize / (2 * Math.atan(Math.PI * this.camera.fov / 360));
        const fitWidthDistance = fitHeightDistance / this.camera.aspect;
        const distance = 1.5 * Math.max(fitHeightDistance, fitWidthDistance);

        this.controls.target.copy(center);
        const direction = this.camera.position.clone().sub(center).normalize();
        this.camera.position.copy(center).add(direction.multiplyScalar(distance));
        
        this.camera.near = distance / 100;
        this.camera.far = distance * 100;
        this.camera.updateProjectionMatrix();

        this.controls.update();
        Telemetry.log('VIEW', 'Fit to view executed');
    }
}