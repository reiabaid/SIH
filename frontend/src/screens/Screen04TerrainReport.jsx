import React, { useState, useRef, useEffect } from 'react';
import { Globe, Sun, Download, AlertCircle, ArrowLeft } from 'lucide-react';
import * as THREE from 'three';

const API_BASE = import.meta.env.PROD ? '' : 'http://127.0.0.1:8000';

// Real deliverable files written by src/deliverable.py + src/cnet.py --
// nothing here is fabricated (no PDF report, no bundled .tar, no "GCP
// validation package" -- those don't exist in the pipeline).
const ARTEFACTS = [
  { file: 'registered_a_to_b.tif', label: 'Registered raster', desc: 'GeoTIFF warped into the reference frame' },
  { file: 'match_points.csv', label: 'Match points (CSV)', desc: 'Tie-points with pixel + geo coordinates' },
  { file: 'match_points.geojson', label: 'Match points (GeoJSON)', desc: 'Tie-point lines as GeoJSON' },
  { file: 'overlay_rgb.png', label: 'Overlay preview', desc: 'Red/green alignment, cropped to the overlap and downscaled (preview only; full resolution is in the registered raster)' },
  { file: 'control_network.net', label: 'Control network', desc: 'ISIS PVL format, ready for jigsaw' },
  { file: 'metrics.json', label: 'Metrics (raw JSON)', desc: 'Same numbers shown on the Evidence screen, as a machine-readable file' },
];

export default function Screen04TerrainReport({ jobId, selectedProductA, selectedProductB, onBack }) {
  const [sunAzimuth, setSunAzimuth] = useState(118);
  const [sunElevation, setSunElevation] = useState(27);
  const canvasRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const terrainMeshRef = useRef(null);
  const sunLightRef = useRef(null);
  const sunIndicatorRef = useRef(null);
  const cameraRef = useRef(null);
  const animationIdRef = useRef(null);

  // Generate procedural lunar terrain using Perlin-like noise
  const generateTerrainGeometry = () => {
    const size = 64;
    const detail = 32;
    const geometry = new THREE.IcosahedronGeometry(2, detail);
    
    const positions = geometry.attributes.position;
    const positionArray = positions.array;
    
    // Noise-like function (simple sine-based pseudo-noise)
    const noise = (x, y, z, scale = 1, octaves = 4) => {
      let value = 0;
      let amplitude = 1;
      let frequency = 1;
      let maxValue = 0;
      
      for (let i = 0; i < octaves; i++) {
        const sx = Math.sin(x * frequency * scale + y * frequency * 0.7);
        const sy = Math.sin(y * frequency * scale + z * frequency * 0.3);
        const sz = Math.sin(z * frequency * scale + x * frequency * 0.5);
        value += (sx * sy * sz) * amplitude;
        maxValue += amplitude;
        amplitude *= 0.5;
        frequency *= 2;
      }
      
      return value / maxValue;
    };
    
    // Displace vertices outward based on noise
    for (let i = 0; i < positionArray.length; i += 3) {
      const x = positionArray[i];
      const y = positionArray[i + 1];
      const z = positionArray[i + 2];
      
      const length = Math.sqrt(x * x + y * y + z * z);
      const n = noise(x, y, z, 2, 4);
      const displacement = 0.3 + n * 0.3;
      
      const scale = length + displacement;
      positionArray[i] = (x / length) * scale;
      positionArray[i + 1] = (y / length) * scale;
      positionArray[i + 2] = (z / length) * scale;
    }
    
    positions.needsUpdate = true;
    geometry.computeVertexNormals();
    return geometry;
  };

  // Initialize Three.js scene
  useEffect(() => {
    if (!canvasRef.current) return;
    
    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0a);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(
      75,
      canvasRef.current.clientWidth / canvasRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 3.5;
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ 
      canvas: canvasRef.current, 
      antialias: true, 
      alpha: false 
    });
    renderer.setSize(canvasRef.current.clientWidth, canvasRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    rendererRef.current = renderer;

    // Create lunar terrain
    const terrainGeometry = generateTerrainGeometry();
    const terrainMaterial = new THREE.MeshStandardMaterial({
      color: 0x888888,
      roughness: 0.85,
      metalness: 0.1,
      side: THREE.FrontSide,
    });
    const terrainMesh = new THREE.Mesh(terrainGeometry, terrainMaterial);
    terrainMesh.castShadow = true;
    terrainMesh.receiveShadow = true;
    terrainMeshRef.current = terrainMesh;
    scene.add(terrainMesh);

    // Ambient light (moonlit night)
    const ambientLight = new THREE.AmbientLight(0x1a1a2e, 0.3);
    scene.add(ambientLight);

    // Sun directional light
    const sunLight = new THREE.DirectionalLight(0xffffff, 1.2);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.camera.near = 0.1;
    sunLight.shadow.camera.far = 100;
    sunLight.shadow.camera.left = -3;
    sunLight.shadow.camera.right = 3;
    sunLight.shadow.camera.top = 3;
    sunLight.shadow.camera.bottom = -3;
    sunLightRef.current = sunLight;
    scene.add(sunLight);

    // Sun indicator (small glowing sphere)
    const sunGeometry = new THREE.SphereGeometry(0.15, 16, 16);
    const sunMaterial = new THREE.MeshBasicMaterial({
      color: 0xffff00,
      emissive: 0xffaa00,
      emissiveIntensity: 1.5,
    });
    const sunIndicator = new THREE.Mesh(sunGeometry, sunMaterial);
    sunIndicatorRef.current = sunIndicator;
    scene.add(sunIndicator);

    // Add glow effect to sun
    const glowGeometry = new THREE.SphereGeometry(0.2, 16, 16);
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: 0xffff00,
      transparent: true,
      opacity: 0.2,
    });
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    sunIndicator.add(glow);

    // Handle mouse interaction
    let isDragging = false;
    let previousMousePosition = { x: 0, y: 0 };
    const rotation = { x: 0, y: 0 };

    canvasRef.current.addEventListener('mousedown', (e) => {
      isDragging = true;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    });

    canvasRef.current.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const deltaX = e.clientX - previousMousePosition.x;
      const deltaY = e.clientY - previousMousePosition.y;
      rotation.y += deltaX * 0.005;
      rotation.x += deltaY * 0.005;
      previousMousePosition = { x: e.clientX, y: e.clientY };
      terrainMesh.rotation.y = rotation.y;
      terrainMesh.rotation.x = rotation.x;
    });

    canvasRef.current.addEventListener('mouseup', () => {
      isDragging = false;
    });

    canvasRef.current.addEventListener('wheel', (e) => {
      e.preventDefault();
      camera.position.z += e.deltaY * 0.002;
      camera.position.z = Math.max(2, Math.min(8, camera.position.z));
    });

    // Animation loop
    const animate = () => {
      animationIdRef.current = requestAnimationFrame(animate);

      // Update sun position based on sliders
      if (sunLightRef.current && sunIndicatorRef.current) {
        const azimuthRad = (sunAzimuth * Math.PI) / 180;
        const elevationRad = (sunElevation * Math.PI) / 180;
        
        const distance = 5;
        const sunX = distance * Math.cos(azimuthRad) * Math.cos(elevationRad);
        const sunY = distance * Math.sin(elevationRad);
        const sunZ = distance * Math.sin(azimuthRad) * Math.cos(elevationRad);
        
        sunLightRef.current.position.set(sunX, sunY, sunZ);
        sunLightRef.current.target.position.set(0, 0, 0);
        sunIndicatorRef.current.position.set(sunX, sunY, sunZ);
      }

      renderer.render(scene, camera);
    };

    animate();

    // Handle window resize
    const handleResize = () => {
      if (!canvasRef.current) return;
      const width = canvasRef.current.clientWidth;
      const height = canvasRef.current.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (animationIdRef.current) cancelAnimationFrame(animationIdRef.current);
      canvasRef.current?.removeEventListener('mousedown', () => {});
      canvasRef.current?.removeEventListener('mousemove', () => {});
      canvasRef.current?.removeEventListener('mouseup', () => {});
      canvasRef.current?.removeEventListener('wheel', () => {});
      renderer.dispose();
      terrainGeometry.dispose();
      terrainMaterial.dispose();
    };
  }, []);

  // Update sun position when sliders change
  useEffect(() => {
    if (!sunLightRef.current || !sunIndicatorRef.current) return;
    
    const azimuthRad = (sunAzimuth * Math.PI) / 180;
    const elevationRad = (sunElevation * Math.PI) / 180;
    
    const distance = 5;
    const sunX = distance * Math.cos(azimuthRad) * Math.cos(elevationRad);
    const sunY = distance * Math.sin(elevationRad);
    const sunZ = distance * Math.sin(azimuthRad) * Math.cos(elevationRad);
    
    sunLightRef.current.position.set(sunX, sunY, sunZ);
    sunLightRef.current.target.position.set(0, 0, 0);
    sunIndicatorRef.current.position.set(sunX, sunY, sunZ);
  }, [sunAzimuth, sunElevation]);

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2a2a2a] pb-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            {onBack && (
              <button onClick={onBack} className="p-1.5 bg-[#1c1c1c] hover:bg-[#242424] rounded-md transition-colors border border-[#2a2a2a]">
                <ArrowLeft className="w-4 h-4 text-cyan-400" />
              </button>
            )}
            <h2 className="text-lg font-display font-semibold text-slate-200 flex items-center space-x-2">
              <Globe className="w-5 h-5 text-cyan-400" />
              <span>Terrain &amp; export</span>
            </h2>
          </div>
          <p className="text-xs text-slate-500 font-mono mt-0.5 ml-11">
            Illumination preview and the registration deliverable for this job.
          </p>
        </div>

        {selectedProductA && selectedProductB && (
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-500 bg-[#141414] border border-[#2a2a2a] px-3 py-1.5 rounded-md">
            <span className="text-slate-600">PAIRED:</span>
            <span className="text-cyan-400 font-medium">{selectedProductA.product_id} &amp; {selectedProductB.product_id}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="relative bg-[#141414] border border-[#2a2a2a] rounded-md h-[360px] overflow-hidden flex items-center justify-center">
            <canvas ref={canvasRef} className="w-full h-full" />

            <div className="absolute top-4 left-4 bg-[#141414]/90 border border-[#2a2a2a] p-3 rounded-md text-xs font-mono">
              <div className="text-cyan-400 font-semibold">3D Lunar Terrain</div>
              <div className="text-slate-500 text-[11px]">Procedural terrain with real-time sun lighting</div>
            </div>

            <div className="absolute bottom-4 left-4 bg-[#141414]/95 border border-[#2a2a2a] p-4 rounded-md text-xs font-mono space-y-3 w-72">
              <div className="flex items-center justify-between text-cyan-400 font-semibold">
                <span className="flex items-center space-x-1.5">
                  <Sun className="w-4 h-4 text-amber-500" />
                  <span>Sun angle</span>
                </span>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>AZIMUTH:</span>
                  <span>{sunAzimuth}°</span>
                </div>
                <input type="range" min="0" max="360" value={sunAzimuth}
                  onChange={(e) => setSunAzimuth(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500" />
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>ELEVATION:</span>
                  <span>{sunElevation}°</span>
                </div>
                <input type="range" min="5" max="85" value={sunElevation}
                  onChange={(e) => setSunElevation(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500" />
              </div>
              <div className="text-[11px] text-slate-500 pt-2 border-t border-[#2a2a2a]">
                Drag to rotate • Scroll to zoom
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="glass-panel p-5 space-y-3 font-mono text-xs">
            <div className="text-slate-400 font-semibold uppercase tracking-wide border-b border-[#2a2a2a] pb-2">
              DELIVERABLE ARTEFACTS
            </div>

            {!jobId ? (
              <div className="flex items-center space-x-2 text-slate-500 text-[11px] py-4">
                <AlertCircle className="w-4 h-4" />
                <span>No completed job yet.</span>
              </div>
            ) : (
              <div className="space-y-2">
                {ARTEFACTS.map((a) => (
                  <a
                    key={a.file}
                    href={`${API_BASE}/jobs/${jobId}/artefacts/${a.file}`}
                    download={a.file}
                    className="flex items-start justify-between space-x-3 p-2.5 rounded-md bg-[#141414] border border-[#2a2a2a] hover:border-cyan-500/60 transition group"
                  >
                    <div>
                      <div className="text-slate-300 font-medium group-hover:text-cyan-400">{a.label}</div>
                      <div className="text-[11px] text-slate-500">{a.desc}</div>
                    </div>
                    <Download className="w-4 h-4 text-slate-600 group-hover:text-cyan-500 shrink-0 mt-0.5" />
                  </a>
                ))}
              </div>
            )}

            <div className="p-3 rounded-md bg-cyan-950/40 border border-cyan-800 text-[11px] text-cyan-300 leading-relaxed">
              Control network is written to the documented ISIS PVL spec and round-trips through an
              independent parser. Not yet validated by running ISIS jigsaw itself.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
