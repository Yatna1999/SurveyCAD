"""DWG generator for SurveyCAD (DXF → DWG via ODA File Converter)."""

import io, os, logging, tempfile, shutil
from utils.dxf_generator import generate_dxf_doc

logger = logging.getLogger(__name__)


def generate_dwg_stream(rows, text_height=1.0, offset=True,
                        polyline_codes=None, units="meters"):
    """Build DXF doc → save temp → convert to DWG via ODA → return bytes."""
    doc = generate_dxf_doc(rows=rows, text_height=text_height, offset=offset,
                           polyline_codes=polyline_codes, units=units)

    tmp = tempfile.mkdtemp(prefix="surveycad_")
    dxf_path = os.path.join(tmp, "survey.dxf")
    dwg_path = os.path.join(tmp, "survey.dwg")

    try:
        doc.saveas(dxf_path)

        from ezdxf.addons import odafc
        import glob, platform

        # Auto-detect ODA File Converter on Windows
        if platform.system() == "Windows":
            for pattern in [r"C:\Program Files\ODA\*\ODAFileConverter.exe",
                            r"C:\Program Files (x86)\ODA\*\ODAFileConverter.exe",
                            r"C:\Program Files\ODAFileConverter*\ODAFileConverter.exe"]:
                hits = glob.glob(pattern)
                if hits:
                    odafc.win_exec_path = hits[-1]; break

        if not odafc.is_installed():
            raise RuntimeError(
                "DWG conversion requires the free ODA File Converter. "
                "Download from https://www.opendesign.com/guestfiles/oda_file_converter "
                "and install it, then restart the server."
            )

        odafc.convert(dxf_path, dwg_path, version="R2018")

        with open(dwg_path, "rb") as f:
            return io.BytesIO(f.read())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
