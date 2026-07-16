import re

def append_to_main(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_endpoints = """

# ──────────────────────────────────────────────
# REST — Ajustes y Configuración
# ──────────────────────────────────────────────
from schemas import CameraConfigUpdate, SystemSettingsUpdate

@app.get("/api/settings", summary="Obtener configuración general")
def get_settings(db: Session = Depends(database.get_db)):
    settings = db.query(models.SystemSettings).first()
    if not settings:
        settings = models.SystemSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@app.put("/api/settings", summary="Actualizar configuración general")
def update_settings(data: SystemSettingsUpdate, db: Session = Depends(database.get_db)):
    settings = db.query(models.SystemSettings).first()
    if not settings:
        settings = models.SystemSettings()
        db.add(settings)
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    
    db.commit()
    db.refresh(settings)
    return {"ok": True, "settings": settings}

@app.get("/api/cameras/config", summary="Lista configuración extendida de cámaras")
def get_cameras_config(db: Session = Depends(database.get_db)):
    # Sincronizar las camaras desde .env a la base de datos temporalmente si no existen
    for cam_conf in settings.cameras:
        c_db = db.query(models.Camera).filter(models.Camera.camera_id == cam_conf.camera_id).first()
        if not c_db:
            c_db = models.Camera(
                camera_id=cam_conf.camera_id,
                ip_address=cam_conf.ip,
                name=cam_conf.name,
                zone=cam_conf.group
            )
            db.add(c_db)
    db.commit()
    return db.query(models.Camera).all()

@app.put("/api/cameras/{cam_id}", summary="Actualizar configuración de cámara")
def update_camera(cam_id: int, data: CameraConfigUpdate, db: Session = Depends(database.get_db)):
    c_db = db.query(models.Camera).filter(models.Camera.id == cam_id).first()
    if not c_db:
        return {"ok": False, "error": "Cámara no encontrada"}
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(c_db, key, value)
    
    db.commit()
    db.refresh(c_db)
    return {"ok": True, "camera": c_db}
"""
    
    # Solo agregar si no se ha agregado antes
    if "def update_settings" not in content:
        content = content.replace('if __name__ == "__main__":', new_endpoints + '\nif __name__ == "__main__":')
        
    # Arreglar modelo de base de datos
    # Necesito asegurarme de que Camera tenga camera_id en models.py
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

append_to_main('backend/main.py')
