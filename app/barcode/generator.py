from pathlib import Path
from app.config import ROOT

def generate_barcode(employee_id: str, output_dir: Path | None=None) -> Path:
    """Generate a Code 128 PNG whose payload is exclusively the employee ID."""
    if not employee_id.startswith('EMP'): raise ValueError('Invalid employee ID')
    try:
        import barcode
        from barcode.writer import ImageWriter
    except ImportError as e: raise RuntimeError('Install python-barcode[pillow] to generate barcodes') from e
    output_dir=output_dir or ROOT/'barcodes'; output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/employee_id
    barcode.get('code128',employee_id,writer=ImageWriter()).save(str(target))
    return target.with_suffix('.png')
