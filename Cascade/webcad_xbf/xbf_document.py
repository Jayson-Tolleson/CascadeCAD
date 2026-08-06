import json
import struct
from pathlib import Path

class XBFDocument:
    """
    Handles the Exchange Binary Format (XBF) specification for CascadeCAD.
    Acts as the neutral single source of truth between imports (STEP/IGES/STL) 
    and the browser editing/rendering/analysis engines.
    """
    
    HEADER_MAGIC = b"XBF1"

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.metadata = {
            "format": "CascadeCAD XBF",
            "version": "1.0.0",
            "units": "millimeters"
        }
        self.assemblies = {}
        self.brep_data = {}
        self.mesh_data = {}
        self.tessellations = {}

    def import_cad_file(self, file_path: str) -> str:
        """
        Simulates ingestion from STEP/IGES/FCStd/STL via OpenCASCADE 
        and extracts normalized XBF components.
        """
        path = Path(file_path)
        asset_id = path.stem
        
        # In a full OCC backend, pythonocc-core parses the file here.
        # For this foundation patch, we extract structural nodes and mock the topology.
        self.assemblies[asset_id] = {
            "source_file": path.name,
            "root_nodes": [f"{asset_id}_root"]
        }
        
        # Store mock B-Rep topology and cached tessellations
        self.brep_data[asset_id] = {
            "topology_type": "Compound",
            "shape_count": 1
        }
        
        self.mesh_data[asset_id] = {
            "vertex_count": 1240,
            "triangle_count": 2480
        }
        
        self.tessellations[asset_id] = {
            "lod_level": 0,
            "cached": True
        }
        
        return asset_id

    def serialize_to_bytes(self) -> bytes:
        """Packs metadata, assemblies, B-Rep data, and meshes into the binary XBF structure."""
        payload = {
            "metadata": self.metadata,
            "assemblies": self.assemblies,
            "brep_data": self.brep_data,
            "mesh_data": self.mesh_data,
            "tessellations": self.tessellations
        }
        json_bytes = json.dumps(payload, indent=2).encode("utf-8")
        
        # Format: [Magic 4 bytes][JSON Length 4 bytes][JSON Payload]
        header = self.HEADER_MAGIC + struct.pack(">I", len(json_bytes))
        return header + json_bytes

    @classmethod
    def deserialize_from_bytes(cls, data: bytes):
        """Unpacks an XBF binary blob back into a document instance."""
        magic = data[:4]
        if magic != cls.HEADER_MAGIC:
            raise ValueError("Invalid XBF file signature.")
            
        json_len = struct.unpack(">I", data[4:8])[0]
        payload = json.loads(data[8:8+json_len].decode("utf-8"))
        
        doc = cls(payload["metadata"].get("project_name", "ImportedProject"))
        doc.metadata = payload["metadata"]
        doc.assemblies = payload["assemblies"]
        doc.brep_data = payload["brep_data"]
        doc.mesh_data = payload["mesh_data"]
        doc.tessellations = payload["tessellations"]
        return doc

    def save(self, output_path: str):
        with open(output_path, "wb") as f:
            f.write(self.serialize_to_bytes())
