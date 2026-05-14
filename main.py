from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import psycopg2
import psycopg2.extras
import os
import hashlib
import secrets

app = FastAPI(title="Pastelería - Sistema de Costeo", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("DATABASE_URL")

# ─────────────────────────────────────────
# Base de datos
# ─────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ingredientes (
            id          SERIAL PRIMARY KEY,
            nombre      TEXT UNIQUE NOT NULL,
            unidad      TEXT NOT NULL,
            precio      REAL NOT NULL,
            updated_at  TEXT DEFAULT (NOW()::text)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS recetas (
            id              SERIAL PRIMARY KEY,
            nombre          TEXT UNIQUE NOT NULL,
            gastos_extra    REAL DEFAULT 300,
            margen          REAL DEFAULT 3.0,
            notas           TEXT,
            created_at      TEXT DEFAULT (NOW()::text)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS receta_ingredientes (
            id              SERIAL PRIMARY KEY,
            receta_id       INTEGER NOT NULL REFERENCES recetas(id) ON DELETE CASCADE,
            ingrediente_id  INTEGER NOT NULL REFERENCES ingredientes(id),
            cantidad        REAL NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          SERIAL PRIMARY KEY,
            usuario     TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            nombre      TEXT NOT NULL,
            rol         TEXT DEFAULT 'usuario'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            token       TEXT PRIMARY KEY,
            usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id          SERIAL PRIMARY KEY,
            nombre      TEXT NOT NULL,
            telefono    TEXT,
            email       TEXT,
            notas       TEXT,
            created_at  TEXT DEFAULT (NOW()::text)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            id          SERIAL PRIMARY KEY,
            cliente_id  INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
            titulo      TEXT NOT NULL,
            notas       TEXT,
            estado      TEXT DEFAULT 'borrador',
            created_at  TEXT DEFAULT (NOW()::text)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS presupuesto_items (
            id              SERIAL PRIMARY KEY,
            presupuesto_id  INTEGER NOT NULL REFERENCES presupuestos(id) ON DELETE CASCADE,
            receta_id       INTEGER REFERENCES recetas(id) ON DELETE SET NULL,
            descripcion     TEXT NOT NULL,
            cantidad        INTEGER DEFAULT 1,
            precio_unit     REAL NOT NULL,
            precio_total    REAL NOT NULL
        )
    """)
    conn.commit()

    # Crear usuario admin por defecto si no existe
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()["count"] == 0:
        pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute(
            "INSERT INTO usuarios (usuario, password, nombre, rol) VALUES (%s, %s, %s, %s)",
            ("admin", pwd_hash, "Administrador", "admin")
        )
        conn.commit()

    # Cargar ingredientes si la tabla está vacía
    c.execute("SELECT COUNT(*) FROM ingredientes")
    count = c.fetchone()["count"]
    if count == 0:
        ingredientes = [
            ("Manteca", "KG", 2200),
            ("Azucar", "KG", 1200),
            ("Leche", "LT", 1000),
            ("Huevo", "UN", 130),
            ("Dulce de Leche", "KG", 3100),
            ("Limon", "UN", 120),
            ("Leche Condensada", "UN", 2000),
            ("Frutilla", "KG", 1800),
            ("Harina", "KG", 900),
            ("Durazno", "KG", 2000),
            ("Crema", "KG", 6000),
            ("Chocolate", "KG", 6500),
            ("Esencia", "LT", 1200),
            ("Fecula", "KG", 1300),
            ("Bicarbonato", "KG", 9800),
            ("Polvo de Hornear", "KG", 8000),
            ("Coco", "KG", 7000),
            ("Azucar Impalpable", "KG", 2400),
            ("Queso Crema", "KG", 6000),
            ("Cacao Amargo", "KG", 12000),
            ("Oreo", "KG", 3200),
            ("Pasta de Torta", "KG", 4000),
            ("Chocolinas", "KG", 3600),
            ("Pasta de Mani", "KG", 7000),
            ("Nueces", "KG", 10000),
            ("Almendras", "KG", 12000),
            ("Azucar Mascabo", "KG", 2000),
            ("Azucar Negra", "KG", 2500),
            ("Miel", "KG", 4000),
            ("Leche de Coco", "LT", 2000),
            ("Glucosa", "KG", 2000),
            ("Aceite", "LT", 1500),
            ("Almibar", "LT", 1200),
            ("Dulce de Membrillo", "KG", 5000),
            ("Merengue en Polvo", "KG", 9000),
            ("Leche en Polvo", "KG", 9000),
            ("Crema Vegetal", "KG", 6000),
            ("Pulpa Frutilla", "KG", 3000),
            ("Pulpa Frambuesa", "KG", 5000),
            ("Pulpa Durazno", "KG", 4000),
            ("Pulpa Frutos Rojos", "KG", 5500),
            ("Vainilla", "LT", 2000),
            ("Mani", "KG", 7000),
            ("Whisky", "LT", 3000),
            ("Chip de Chocolate", "KG", 7600),
            ("Gelatina ss", "KG", 19000),
            ("Cafe Instantaneo", "KG", 8000),
        ]
        c.executemany(
            "INSERT INTO ingredientes (nombre, unidad, precio) VALUES (%s, %s, %s)",
            ingredientes
        )
        conn.commit()

    # Cargar recetas si la tabla está vacía
    c.execute("SELECT COUNT(*) FROM recetas")
    count_r = c.fetchone()["count"]
    if count_r == 0:
        def get_id(nombre):
            c.execute("SELECT id FROM ingredientes WHERE nombre=%s", (nombre,))
            row = c.fetchone()
            return row["id"] if row else None

        recetas_data = [
            {
                "nombre": "Torta Base",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Huevo", 6), ("Azucar", 400), ("Harina", 400), ("Aceite", 25),
                    ("Leche", 25), ("Dulce de Leche", 400), ("Azucar", 300),
                    ("Huevo", 1), ("Manteca", 400), ("Esencia", 10),
                    ("Almibar", 100), ("Pulpa Frutilla", 100),
                ]
            },
            {
                "nombre": "Tarta Frutilla",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 280), ("Manteca", 100), ("Azucar", 100),
                    ("Huevo", 1), ("Crema", 250), ("Dulce de Leche", 150),
                    ("Frutilla", 400), ("Azucar Impalpable", 30),
                ]
            },
            {
                "nombre": "Tarta Durazno",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 280), ("Manteca", 100), ("Azucar", 100),
                    ("Huevo", 1), ("Crema", 250), ("Dulce de Leche", 150),
                    ("Durazno", 500), ("Azucar Impalpable", 30),
                ]
            },
            {
                "nombre": "Tarta Coco",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 280), ("Manteca", 100), ("Azucar", 100),
                    ("Huevo", 1), ("Coco", 100), ("Dulce de Leche", 500), ("Azucar", 200),
                ]
            },
            {
                "nombre": "Tarta Bombon",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 280), ("Manteca", 100), ("Azucar", 100),
                    ("Huevo", 1), ("Chocolate", 120), ("Dulce de Leche", 400), ("Crema", 120),
                ]
            },
            {
                "nombre": "Lemon Pie",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 280), ("Manteca", 100), ("Azucar", 100),
                    ("Huevo", 1), ("Limon", 1), ("Azucar", 120),
                    ("Huevo", 3), ("Fecula", 40), ("Manteca", 25), ("Azucar", 250),
                ]
            },
            {
                "nombre": "Brownie",
                "gastos_extra": 300,
                "margen": 3.0,
                "notas": "Salen 2 unidades de 20cm de diámetro",
                "ingredientes": [
                    ("Harina", 100), ("Manteca", 200), ("Azucar", 300),
                    ("Huevo", 5), ("Chocolate", 150), ("Cacao Amargo", 30),
                    ("Cafe Instantaneo", 8), ("Vainilla", 10), ("Dulce de Leche", 800),
                    ("Crema", 400), ("Azucar Impalpable", 50),
                ]
            },
            {
                "nombre": "Cheese Cake",
                "gastos_extra": 300,
                "margen": 3.0,
                "notas": "Salen 2 unidades de 20cm de diámetro",
                "ingredientes": [
                    ("Harina", 200), ("Azucar", 200), ("Huevo", 4),
                    ("Azucar", 100), ("Huevo", 3), ("Azucar", 120),
                    ("Queso Crema", 300), ("Crema", 200), ("Gelatina ss", 8),
                    ("Whisky", 40), ("Limon", 1),
                ]
            },
            {
                "nombre": "Alfajores Mani",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 260), ("Manteca", 120), ("Vainilla", 10),
                    ("Azucar", 120), ("Huevo", 3), ("Fecula", 40),
                    ("Mani", 100), ("Polvo de Hornear", 5),
                    ("Bicarbonato", 3), ("Cacao Amargo", 5),
                ]
            },
            {
                "nombre": "Alfajores Coco",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 100), ("Manteca", 100), ("Vainilla", 10),
                    ("Azucar", 50), ("Huevo", 1), ("Fecula", 60),
                    ("Coco", 100), ("Polvo de Hornear", 5),
                ]
            },
            {
                "nombre": "Alfajores Nueces",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 300), ("Manteca", 200), ("Vainilla", 10),
                    ("Azucar", 200), ("Huevo", 1), ("Fecula", 100),
                    ("Cacao Amargo", 20), ("Miel", 40), ("Nueces", 100),
                    ("Dulce de Leche", 30), ("Whisky", 30), ("Cacao Amargo", 30),
                ]
            },
            {
                "nombre": "Alfajores Cordobeses",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 210), ("Manteca", 115), ("Azucar", 100),
                    ("Huevo", 1), ("Fecula", 180), ("Cacao Amargo", 20),
                    ("Miel", 50), ("Nueces", 100), ("Dulce de Leche", 30),
                    ("Polvo de Hornear", 3), ("Azucar", 300),
                ]
            },
            {
                "nombre": "Alfajores Cookies",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 125), ("Manteca", 120), ("Azucar", 60),
                    ("Huevo", 1), ("Fecula", 100), ("Dulce de Leche", 30),
                    ("Chip de Chocolate", 80),
                ]
            },
            {
                "nombre": "Alfajores Maicena",
                "gastos_extra": 300,
                "margen": 3.0,
                "ingredientes": [
                    ("Harina", 200), ("Manteca", 200), ("Azucar", 150),
                    ("Huevo", 3), ("Fecula", 200), ("Bicarbonato", 5),
                ]
            },
        ]

        for r in recetas_data:
            notas = r.get("notas", None)
            c.execute(
                "INSERT INTO recetas (nombre, gastos_extra, margen, notas) VALUES (%s, %s, %s, %s) RETURNING id",
                (r["nombre"], r["gastos_extra"], r["margen"], notas)
            )
            receta_id = c.fetchone()["id"]
            for ing_nombre, cantidad in r["ingredientes"]:
                ing_id = get_id(ing_nombre)
                if ing_id:
                    c.execute(
                        "INSERT INTO receta_ingredientes (receta_id, ingrediente_id, cantidad) VALUES (%s, %s, %s)",
                        (receta_id, ing_id, cantidad)
                    )
        conn.commit()
    c.close()
    conn.close()

init_db()

# ─────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────

class IngredienteCreate(BaseModel):
    nombre: str
    unidad: str
    precio: float

class IngredienteUpdate(BaseModel):
    nombre: Optional[str] = None
    unidad: Optional[str] = None
    precio: Optional[float] = None

class RecetaCreate(BaseModel):
    nombre: str
    gastos_extra: Optional[float] = 300
    margen: Optional[float] = 3.0
    notas: Optional[str] = None

class RecetaUpdate(BaseModel):
    nombre: Optional[str] = None
    gastos_extra: Optional[float] = None
    margen: Optional[float] = None
    notas: Optional[str] = None

class RecetaIngredienteItem(BaseModel):
    ingrediente_id: int
    cantidad: float

# ─────────────────────────────────────────
# INGREDIENTES
# ─────────────────────────────────────────

@app.get("/ingredientes", tags=["Ingredientes"])
def listar_ingredientes(authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM ingredientes ORDER BY nombre")
    rows = c.fetchall()
    c.close()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/ingredientes", tags=["Ingredientes"], summary="Crear nuevo ingrediente")
def crear_ingrediente(data: IngredienteCreate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO ingredientes (nombre, unidad, precio) VALUES (%s, %s, %s) RETURNING *",
            (data.nombre.strip(), data.unidad.upper(), data.precio)
        )
        row = c.fetchone()
        conn.commit()
        c.close()
        conn.close()
        return dict(row)
    except Exception:
        conn.rollback()
        c.close()
        conn.close()
        raise HTTPException(400, f"Ya existe un ingrediente con el nombre '{data.nombre}'")

@app.put("/ingredientes/{ing_id}", tags=["Ingredientes"], summary="Actualizar ingrediente")
def actualizar_ingrediente(ing_id: int, data: IngredienteUpdate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM ingredientes WHERE id=%s", (ing_id,))
    row = c.fetchone()
    if not row:
        c.close()
        conn.close()
        raise HTTPException(404, "Ingrediente no encontrado")
    campos = data.dict(exclude_none=True)
    if not campos:
        c.close()
        conn.close()
        return dict(row)
    sets = ", ".join(f"{k}=%s" for k in campos)
    sets += ", updated_at=NOW()::text"
    vals = list(campos.values()) + [ing_id]
    c.execute(f"UPDATE ingredientes SET {sets} WHERE id=%s RETURNING *", vals)
    row = c.fetchone()
    conn.commit()
    c.close()
    conn.close()
    return dict(row)

@app.delete("/ingredientes/{ing_id}", tags=["Ingredientes"], summary="Eliminar ingrediente")
def eliminar_ingrediente(ing_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM receta_ingredientes WHERE ingrediente_id=%s", (ing_id,))
    en_uso = c.fetchone()["count"]
    if en_uso > 0:
        c.close()
        conn.close()
        raise HTTPException(400, f"No se puede eliminar: el ingrediente se usa en {en_uso} receta(s)")
    c.execute("DELETE FROM ingredientes WHERE id=%s", (ing_id,))
    conn.commit()
    c.close()
    conn.close()
    return {"mensaje": "Ingrediente eliminado"}

# ─────────────────────────────────────────
# RECETAS
# ─────────────────────────────────────────

def calcular_costo_receta_v2(conn, receta_id):
    c = conn.cursor()
    c.execute("""
        SELECT ri.cantidad, i.precio, i.unidad
        FROM receta_ingredientes ri
        JOIN ingredientes i ON ri.ingrediente_id = i.id
        WHERE ri.receta_id = %s
    """, (receta_id,))
    rows = c.fetchall()
    c.close()
    total = 0
    for r in rows:
        if r["unidad"] == "UN":
            total += r["cantidad"] * r["precio"]
        else:
            total += (r["cantidad"] / 1000) * r["precio"]
    return round(total, 2)

@app.get("/recetas", tags=["Recetas"], summary="Listar todas las recetas con costos calculados")
def listar_recetas(authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM recetas ORDER BY nombre")
    recetas = c.fetchall()
    c.close()
    resultado = []
    for r in recetas:
        costo = calcular_costo_receta_v2(conn, r["id"])
        precio_final = round((costo + r["gastos_extra"]) * r["margen"], 2)
        resultado.append({
            **dict(r),
            "costo_ingredientes": costo,
            "costo_total": round(costo + r["gastos_extra"], 2),
            "precio_final": precio_final,
        })
    conn.close()
    return resultado

@app.get("/recetas/{receta_id}", tags=["Recetas"], summary="Detalle de receta con ingredientes")
def obtener_receta(receta_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM recetas WHERE id=%s", (receta_id,))
    r = c.fetchone()
    if not r:
        c.close()
        conn.close()
        raise HTTPException(404, "Receta no encontrada")
    c.execute("""
        SELECT ri.id, ri.cantidad, i.id as ingrediente_id, i.nombre, i.unidad, i.precio,
               CASE WHEN i.unidad='UN' THEN ri.cantidad * i.precio
                    ELSE (ri.cantidad / 1000.0) * i.precio END as costo_real
        FROM receta_ingredientes ri
        JOIN ingredientes i ON ri.ingrediente_id = i.id
        WHERE ri.receta_id = %s
        ORDER BY i.nombre
    """, (receta_id,))
    ingredientes = c.fetchall()
    c.close()
    costo = calcular_costo_receta_v2(conn, receta_id)
    precio_final = round((costo + r["gastos_extra"]) * r["margen"], 2)
    conn.close()
    return {
        **dict(r),
        "costo_ingredientes": costo,
        "costo_total": round(costo + r["gastos_extra"], 2),
        "precio_final": precio_final,
        "ingredientes": [dict(i) for i in ingredientes],
    }

@app.post("/recetas", tags=["Recetas"], summary="Crear nueva receta")
def crear_receta(data: RecetaCreate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO recetas (nombre, gastos_extra, margen, notas) VALUES (%s, %s, %s, %s) RETURNING id",
            (data.nombre, data.gastos_extra, data.margen, data.notas)
        )
        receta_id = c.fetchone()["id"]
        conn.commit()
        c.close()
        conn.close()
        return obtener_receta(receta_id)
    except Exception:
        conn.rollback()
        c.close()
        conn.close()
        raise HTTPException(400, f"Ya existe una receta con el nombre '{data.nombre}'")

@app.put("/recetas/{receta_id}", tags=["Recetas"], summary="Actualizar receta")
def actualizar_receta(receta_id: int, data: RecetaUpdate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM recetas WHERE id=%s", (receta_id,))
    row = c.fetchone()
    if not row:
        c.close()
        conn.close()
        raise HTTPException(404, "Receta no encontrada")
    campos = data.dict(exclude_none=True)
    if campos:
        sets = ", ".join(f"{k}=%s" for k in campos)
        vals = list(campos.values()) + [receta_id]
        c.execute(f"UPDATE recetas SET {sets} WHERE id=%s", vals)
        conn.commit()
    c.close()
    conn.close()
    return obtener_receta(receta_id)

@app.delete("/recetas/{receta_id}", tags=["Recetas"])
def eliminar_receta(receta_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM receta_ingredientes WHERE receta_id=%s", (receta_id,))
    c.execute("DELETE FROM recetas WHERE id=%s", (receta_id,))
    conn.commit()
    c.close()
    conn.close()
    return {"mensaje": "Receta eliminada"}

@app.post("/recetas/{receta_id}/ingredientes", tags=["Recetas"], summary="Agregar ingrediente a receta")
def agregar_ingrediente_receta(receta_id: int, item: RecetaIngredienteItem, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO receta_ingredientes (receta_id, ingrediente_id, cantidad) VALUES (%s, %s, %s)",
        (receta_id, item.ingrediente_id, item.cantidad)
    )
    conn.commit()
    c.close()
    conn.close()
    return obtener_receta(receta_id)

@app.put("/recetas/{receta_id}/ingredientes/{ri_id}", tags=["Recetas"], summary="Actualizar cantidad de ingrediente")
def actualizar_ingrediente_receta(receta_id: int, ri_id: int, item: RecetaIngredienteItem, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE receta_ingredientes SET ingrediente_id=%s, cantidad=%s WHERE id=%s AND receta_id=%s",
        (item.ingrediente_id, item.cantidad, ri_id, receta_id)
    )
    conn.commit()
    c.close()
    conn.close()
    return obtener_receta(receta_id)

@app.delete("/recetas/{receta_id}/ingredientes/{ri_id}", tags=["Recetas"], summary="Quitar ingrediente de receta")
def quitar_ingrediente_receta(receta_id: int, ri_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM receta_ingredientes WHERE id=%s AND receta_id=%s", (ri_id, receta_id))
    conn.commit()
    c.close()
    conn.close()
    return obtener_receta(receta_id)

# ─────────────────────────────────────────
# RESUMEN
# ─────────────────────────────────────────

@app.get("/resumen", tags=["Estadísticas"])
def resumen(authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM ingredientes")
    total_ing = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) FROM recetas")
    total_rec = c.fetchone()["count"]
    c.execute("SELECT id, nombre, gastos_extra, margen FROM recetas")
    recetas = c.fetchall()
    c.close()
    productos = []
    for r in recetas:
        costo = calcular_costo_receta_v2(conn, r["id"])
        precio = round((costo + r["gastos_extra"]) * r["margen"], 2)
        productos.append({"nombre": r["nombre"], "costo": costo, "precio_final": precio})
    conn.close()
    return {
        "total_ingredientes": total_ing,
        "total_recetas": total_rec,
        "productos": sorted(productos, key=lambda x: x["precio_final"], reverse=True)
    }

# ─────────────────────────────────────────
# BACKUP
# ─────────────────────────────────────────

@app.get("/backup", tags=["Admin"], summary="Exportar datos como JSON")
def descargar_backup(authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM ingredientes ORDER BY nombre")
    ingredientes = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM recetas ORDER BY nombre")
    recetas = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM receta_ingredientes")
    relaciones = [dict(r) for r in c.fetchall()]
    c.close()
    conn.close()
    from datetime import datetime
    return {
        "exportado_en": datetime.now().isoformat(),
        "ingredientes": ingredientes,
        "recetas": recetas,
        "receta_ingredientes": relaciones,
    }

# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────

class LoginData(BaseModel):
    usuario: str
    password: str

class UsuarioCreate(BaseModel):
    usuario: str
    password: str
    nombre: str
    rol: Optional[str] = "usuario"

def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def verificar_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "No autorizado")
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.usuario, u.nombre, u.rol
        FROM sesiones s JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.token = %s
    """, (authorization,))
    row = c.fetchone()
    c.close()
    conn.close()
    if not row:
        raise HTTPException(401, "Token inválido")
    return dict(row)

def verificar_admin(authorization: str = Header(None)):
    u = verificar_token(authorization)
    if u["rol"] != "admin":
        raise HTTPException(403, "Se requiere rol admin")
    return u

@app.post("/login", tags=["Auth"])
def login(data: LoginData):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE usuario=%s", (data.usuario,))
    u = c.fetchone()
    if not u or u["password"] != hash_pwd(data.password):
        c.close()
        conn.close()
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    token = secrets.token_hex(32)
    c.execute("INSERT INTO sesiones (token, usuario_id) VALUES (%s, %s)", (token, u["id"]))
    conn.commit()
    c.close()
    conn.close()
    return {
        "token": token,
        "usuario": {"id": u["id"], "usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"]}
    }

@app.get("/usuarios", tags=["Usuarios"])
def listar_usuarios(authorization: str = Header(None)):
    verificar_admin(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, usuario, nombre, rol FROM usuarios ORDER BY nombre")
    rows = [dict(r) for r in c.fetchall()]
    c.close()
    conn.close()
    return rows

@app.post("/usuarios", tags=["Usuarios"])
def crear_usuario(data: UsuarioCreate, authorization: str = Header(None)):
    verificar_admin(authorization)
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO usuarios (usuario, password, nombre, rol) VALUES (%s, %s, %s, %s) RETURNING id, usuario, nombre, rol",
            (data.usuario, hash_pwd(data.password), data.nombre, data.rol)
        )
        row = dict(c.fetchone())
        conn.commit()
        c.close()
        conn.close()
        return row
    except Exception:
        conn.rollback()
        c.close()
        conn.close()
        raise HTTPException(400, f"Ya existe un usuario con ese nombre")

@app.delete("/usuarios/{usuario_id}", tags=["Usuarios"])
def eliminar_usuario(usuario_id: int, authorization: str = Header(None)):
    verificar_admin(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT usuario FROM usuarios WHERE id=%s", (usuario_id,))
    row = c.fetchone()
    if not row:
        c.close()
        conn.close()
        raise HTTPException(404, "Usuario no encontrado")
    if row["usuario"] == "admin":
        c.close()
        conn.close()
        raise HTTPException(400, "No se puede eliminar el usuario admin")
    c.execute("DELETE FROM usuarios WHERE id=%s", (usuario_id,))
    conn.commit()
    c.close()
    conn.close()
    return {"mensaje": "Usuario eliminado"}

# ─────────────────────────────────────────
# PROTEGER ENDPOINTS CON TOKEN
# ─────────────────────────────────────────

# Agrega verificación de token a todos los endpoints que lo necesiten
# usando el Header Authorization

# ─────────────────────────────────────────
# FRONTEND
# ─────────────────────────────────────────

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    with open("frontend/index.html", encoding="utf-8") as f:
        return f.read()

# ─────────────────────────────────────────
# CLIENTES
# ─────────────────────────────────────────

class ClienteCreate(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    notas: Optional[str] = None

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    notas: Optional[str] = None

@app.get("/clientes", tags=["Clientes"])
def listar_clientes(authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM clientes ORDER BY nombre")
    rows = [dict(r) for r in c.fetchall()]
    c.close(); conn.close()
    return rows

@app.post("/clientes", tags=["Clientes"])
def crear_cliente(data: ClienteCreate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO clientes (nombre, telefono, email, notas) VALUES (%s, %s, %s, %s) RETURNING *",
        (data.nombre.strip(), data.telefono, data.email, data.notas)
    )
    row = dict(c.fetchone())
    conn.commit(); c.close(); conn.close()
    return row

@app.put("/clientes/{cliente_id}", tags=["Clientes"])
def actualizar_cliente(cliente_id: int, data: ClienteUpdate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    campos = {k: v for k, v in data.dict().items() if v is not None}
    if campos:
        sets = ", ".join(f"{k}=%s" for k in campos)
        vals = list(campos.values()) + [cliente_id]
        c.execute(f"UPDATE clientes SET {sets} WHERE id=%s RETURNING *", vals)
        row = dict(c.fetchone())
        conn.commit()
    else:
        c.execute("SELECT * FROM clientes WHERE id=%s", (cliente_id,))
        row = dict(c.fetchone())
    c.close(); conn.close()
    return row

@app.delete("/clientes/{cliente_id}", tags=["Clientes"])
def eliminar_cliente(cliente_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM clientes WHERE id=%s", (cliente_id,))
    conn.commit(); c.close(); conn.close()
    return {"mensaje": "Cliente eliminado"}

# ─────────────────────────────────────────
# PRESUPUESTOS
# ─────────────────────────────────────────

class PresupuestoItemIn(BaseModel):
    receta_id: Optional[int] = None
    descripcion: str
    cantidad: int = 1
    precio_unit: float

class PresupuestoCreate(BaseModel):
    cliente_id: Optional[int] = None
    titulo: str
    notas: Optional[str] = None
    estado: Optional[str] = "borrador"
    items: Optional[list[PresupuestoItemIn]] = []

class PresupuestoUpdate(BaseModel):
    cliente_id: Optional[int] = None
    titulo: Optional[str] = None
    notas: Optional[str] = None
    estado: Optional[str] = None

def obtener_presupuesto(presupuesto_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT p.*, cl.nombre as cliente_nombre, cl.telefono as cliente_telefono, cl.email as cliente_email
        FROM presupuestos p
        LEFT JOIN clientes cl ON p.cliente_id = cl.id
        WHERE p.id = %s
    """, (presupuesto_id,))
    p = c.fetchone()
    if not p:
        c.close(); conn.close()
        raise HTTPException(404, "Presupuesto no encontrado")
    c.execute("""
        SELECT pi.*, r.nombre as receta_nombre
        FROM presupuesto_items pi
        LEFT JOIN recetas r ON pi.receta_id = r.id
        WHERE pi.presupuesto_id = %s
        ORDER BY pi.id
    """, (presupuesto_id,))
    items = [dict(i) for i in c.fetchall()]
    total = sum(i["precio_total"] for i in items)
    c.close(); conn.close()
    return {**dict(p), "items": items, "total": round(total, 2)}

@app.get("/presupuestos", tags=["Presupuestos"])
def listar_presupuestos(authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.titulo, p.estado, p.created_at,
               cl.nombre as cliente_nombre,
               COALESCE((SELECT SUM(precio_total) FROM presupuesto_items WHERE presupuesto_id=p.id), 0) as total
        FROM presupuestos p
        LEFT JOIN clientes cl ON p.cliente_id = cl.id
        ORDER BY p.created_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    c.close(); conn.close()
    return rows

@app.get("/presupuestos/{presupuesto_id}", tags=["Presupuestos"])
def obtener_presupuesto_endpoint(presupuesto_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    return obtener_presupuesto(presupuesto_id)

@app.post("/presupuestos", tags=["Presupuestos"])
def crear_presupuesto(data: PresupuestoCreate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO presupuestos (cliente_id, titulo, notas, estado) VALUES (%s, %s, %s, %s) RETURNING id",
        (data.cliente_id, data.titulo.strip(), data.notas, data.estado or "borrador")
    )
    pid = c.fetchone()["id"]
    for item in (data.items or []):
        precio_total = round(item.precio_unit * item.cantidad, 2)
        c.execute(
            "INSERT INTO presupuesto_items (presupuesto_id, receta_id, descripcion, cantidad, precio_unit, precio_total) VALUES (%s, %s, %s, %s, %s, %s)",
            (pid, item.receta_id, item.descripcion, item.cantidad, item.precio_unit, precio_total)
        )
    conn.commit(); c.close(); conn.close()
    return obtener_presupuesto(pid)

@app.put("/presupuestos/{presupuesto_id}", tags=["Presupuestos"])
def actualizar_presupuesto(presupuesto_id: int, data: PresupuestoUpdate, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    campos = {k: v for k, v in data.dict().items() if v is not None}
    if campos:
        sets = ", ".join(f"{k}=%s" for k in campos)
        vals = list(campos.values()) + [presupuesto_id]
        c.execute(f"UPDATE presupuestos SET {sets} WHERE id=%s", vals)
        conn.commit()
    c.close(); conn.close()
    return obtener_presupuesto(presupuesto_id)

@app.delete("/presupuestos/{presupuesto_id}", tags=["Presupuestos"])
def eliminar_presupuesto(presupuesto_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM presupuestos WHERE id=%s", (presupuesto_id,))
    conn.commit(); c.close(); conn.close()
    return {"mensaje": "Presupuesto eliminado"}

@app.post("/presupuestos/{presupuesto_id}/items", tags=["Presupuestos"])
def agregar_item(presupuesto_id: int, item: PresupuestoItemIn, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    precio_total = round(item.precio_unit * item.cantidad, 2)
    c.execute(
        "INSERT INTO presupuesto_items (presupuesto_id, receta_id, descripcion, cantidad, precio_unit, precio_total) VALUES (%s, %s, %s, %s, %s, %s)",
        (presupuesto_id, item.receta_id, item.descripcion, item.cantidad, item.precio_unit, precio_total)
    )
    conn.commit(); c.close(); conn.close()
    return obtener_presupuesto(presupuesto_id)

@app.put("/presupuestos/{presupuesto_id}/items/{item_id}", tags=["Presupuestos"])
def actualizar_item(presupuesto_id: int, item_id: int, item: PresupuestoItemIn, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    precio_total = round(item.precio_unit * item.cantidad, 2)
    c.execute(
        "UPDATE presupuesto_items SET receta_id=%s, descripcion=%s, cantidad=%s, precio_unit=%s, precio_total=%s WHERE id=%s AND presupuesto_id=%s",
        (item.receta_id, item.descripcion, item.cantidad, item.precio_unit, precio_total, item_id, presupuesto_id)
    )
    conn.commit(); c.close(); conn.close()
    return obtener_presupuesto(presupuesto_id)

@app.delete("/presupuestos/{presupuesto_id}/items/{item_id}", tags=["Presupuestos"])
def eliminar_item(presupuesto_id: int, item_id: int, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM presupuesto_items WHERE id=%s AND presupuesto_id=%s", (item_id, presupuesto_id))
    conn.commit(); c.close(); conn.close()
    return obtener_presupuesto(presupuesto_id)

<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Roxi Pastelería · Costeo</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
  :root {
    --crema: #fdf6ee;
    --rosa: #e8a598;
    --rosa-oscuro: #c97b6e;
    --marron: #5c3d2e;
    --marron-claro: #8b5e4a;
    --verde: #7a9e7e;
    --amarillo: #f4c96e;
    --texto: #3a2a22;
    --gris: #9e8a80;
    --blanco: #fff;
    --sombra: 0 4px 24px rgba(92,61,46,0.10);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--crema); font-family: 'DM Sans', sans-serif; color: var(--texto); min-height: 100vh; }

  /* LOGIN */
  #login-screen {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--crema);
  }
  .login-box {
    background: var(--blanco);
    border-radius: 20px;
    box-shadow: 0 8px 40px rgba(92,61,46,0.14);
    padding: 40px 36px;
    width: 100%;
    max-width: 380px;
  }
  .login-box .login-logo {
    text-align: center;
    margin-bottom: 28px;
  }
  .login-box .login-logo .emoji { font-size: 3rem; display: block; margin-bottom: 10px; }
  .login-box .login-logo h2 {
    font-family: 'Playfair Display', serif;
    font-size: 1.6rem;
    color: var(--marron);
    margin-bottom: 4px;
  }
  .login-box .login-logo span { font-size: 0.85rem; color: var(--gris); font-style: italic; }
  .login-field { margin-bottom: 16px; }
  .login-field label { display: block; font-size: 0.78rem; color: var(--gris); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
  .login-field input {
    width: 100%;
    border: 1.5px solid #e8d8cc;
    border-radius: 10px;
    padding: 11px 14px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.95rem;
    background: var(--crema);
    color: var(--texto);
    transition: border-color 0.2s;
  }
  .login-field input:focus { outline: none; border-color: var(--rosa); background: var(--blanco); }
  .btn-login {
    width: 100%;
    background: var(--marron);
    color: var(--crema);
    border: none;
    border-radius: 10px;
    padding: 13px;
    font-family: 'DM Sans', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    margin-top: 8px;
    transition: background 0.2s;
  }
  .btn-login:hover { background: var(--marron-claro); }
  .login-error {
    background: #fce8e4;
    color: var(--rosa-oscuro);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.88rem;
    margin-top: 14px;
    display: none;
    text-align: center;
  }

  /* APP (oculto hasta login) */
  #app-screen { display: none; }

  /* HEADER */
  header {
    background: var(--marron);
    color: var(--crema);
    padding: 18px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 16px rgba(92,61,46,0.18);
  }
  header h1 { font-family: 'Playfair Display', serif; font-size: 1.4rem; font-weight: 700; letter-spacing: 0.02em; }
  header span { font-size: 0.8rem; color: var(--rosa); font-style: italic; }
  .header-user {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .header-user .usuario-badge {
    font-size: 0.82rem;
    color: rgba(253,246,238,0.7);
  }
  .btn-logout {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    color: var(--crema);
    border-radius: 8px;
    padding: 5px 12px;
    cursor: pointer;
    font-size: 0.8rem;
    font-family: 'DM Sans', sans-serif;
    transition: background 0.2s;
  }
  .btn-logout:hover { background: rgba(255,255,255,0.2); }

  /* NAV */
  nav {
    background: var(--blanco);
    display: flex;
    border-bottom: 2px solid #f0e4d8;
    overflow-x: auto;
    scrollbar-width: none;
  }
  nav::-webkit-scrollbar { display: none; }
  nav button {
    flex: 1;
    min-width: 120px;
    padding: 14px 20px;
    border: none;
    background: none;
    cursor: pointer;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--gris);
    border-bottom: 3px solid transparent;
    margin-bottom: -2px;
    transition: all 0.2s;
    white-space: nowrap;
  }
  nav button.active { color: var(--marron); border-bottom-color: var(--rosa); font-weight: 600; }
  nav button:hover:not(.active) { color: var(--marron-claro); background: var(--crema); }

  /* MAIN */
  main { max-width: 900px; margin: 0 auto; padding: 24px 16px 80px; }

  /* CARDS */
  .card {
    background: var(--blanco);
    border-radius: 16px;
    box-shadow: var(--sombra);
    padding: 20px;
    margin-bottom: 16px;
    transition: box-shadow 0.2s;
  }
  .card:hover { box-shadow: 0 8px 32px rgba(92,61,46,0.14); }

  /* STATS */
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .stat {
    background: var(--blanco);
    border-radius: 14px;
    padding: 18px;
    text-align: center;
    box-shadow: var(--sombra);
    border-top: 4px solid var(--rosa);
  }
  .stat .num { font-family: 'Playfair Display', serif; font-size: 2rem; font-weight: 700; color: var(--marron); }
  .stat .lbl { font-size: 0.78rem; color: var(--gris); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }

  /* SECCION TITULO */
  .sec-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.3rem;
    color: var(--marron);
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .sec-title::after { content: ''; flex: 1; height: 1px; background: #f0e4d8; }

  /* TABLA INGREDIENTES */
  .ing-list { display: flex; flex-direction: column; gap: 8px; }
  .ing-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--blanco);
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(92,61,46,0.06);
    border-left: 4px solid var(--crema);
    transition: border-color 0.2s;
  }
  .ing-row:hover { border-left-color: var(--rosa); }
  .ing-nombre { flex: 1; font-weight: 500; font-size: 0.95rem; }
  .ing-unidad { font-size: 0.78rem; color: var(--gris); background: var(--crema); padding: 2px 8px; border-radius: 20px; }
  .ing-precio { display: flex; align-items: center; gap: 6px; }
  .ing-precio span { font-size: 0.8rem; color: var(--gris); }
  .precio-input {
    width: 90px;
    border: 1.5px solid #f0e4d8;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 0.95rem;
    font-family: 'DM Sans', sans-serif;
    text-align: right;
    background: var(--crema);
    color: var(--texto);
    transition: border-color 0.2s;
  }
  .precio-input:focus { outline: none; border-color: var(--rosa); background: var(--blanco); }
  .btn-save {
    background: var(--rosa);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 600;
    transition: background 0.2s;
  }
  .btn-save:hover { background: var(--rosa-oscuro); }

  /* RECETAS GRID */
  .recetas-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
  .receta-card {
    background: var(--blanco);
    border-radius: 16px;
    box-shadow: var(--sombra);
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s;
    border-top: 4px solid var(--amarillo);
    position: relative;
  }
  .receta-card:hover { transform: translateY(-3px); box-shadow: 0 12px 36px rgba(92,61,46,0.14); }
  .receta-card h3 { font-family: 'Playfair Display', serif; font-size: 1.1rem; color: var(--marron); margin-bottom: 12px; }
  .receta-card .notas { font-size: 0.78rem; color: var(--gris); font-style: italic; margin-bottom: 10px; }
  .receta-nums { display: flex; flex-direction: column; gap: 6px; }
  .receta-num-row { display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; }
  .receta-num-row .lbl { color: var(--gris); }
  .receta-num-row .val { font-weight: 600; color: var(--texto); }
  .precio-final-badge {
    margin-top: 14px;
    background: var(--marron);
    color: var(--crema);
    border-radius: 10px;
    padding: 10px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .precio-final-badge .lbl { font-size: 0.78rem; opacity: 0.75; }
  .precio-final-badge .val { font-family: 'Playfair Display', serif; font-size: 1.2rem; font-weight: 700; }

  /* DETALLE RECETA */
  .detalle-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 20px;
  }
  .btn-back {
    background: var(--crema);
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    cursor: pointer;
    font-size: 0.9rem;
    color: var(--marron);
    font-weight: 600;
    transition: background 0.2s;
  }
  .btn-back:hover { background: #f0e4d8; }
  .detalle-titulo { font-family: 'Playfair Display', serif; font-size: 1.5rem; color: var(--marron); }
  .detalle-resumen {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
  }
  .detalle-stat {
    background: var(--crema);
    border-radius: 12px;
    padding: 14px;
    text-align: center;
  }
  .detalle-stat .num { font-family: 'Playfair Display', serif; font-size: 1.4rem; font-weight: 700; color: var(--marron); }
  .detalle-stat .lbl { font-size: 0.75rem; color: var(--gris); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }

  .ing-detalle-row {
    background: var(--crema);
    border-radius: 12px;
    margin-bottom: 8px;
    font-size: 0.9rem;
    border: 1.5px solid transparent;
    transition: border-color 0.2s;
    overflow: hidden;
  }
  .ing-detalle-row:hover { border-color: #e8d8cc; }
  .ing-detalle-row.editando { border-color: var(--rosa); background: var(--blanco); }

  /* Fila vista (compacta) */
  .ing-row-vista {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
  }
  .ing-row-vista .nombre { flex: 1; font-weight: 500; }
  .ing-row-vista .cant { color: var(--gris); font-size: 0.82rem; min-width: 70px; }
  .ing-row-vista .costo { font-weight: 600; color: var(--marron-claro); min-width: 70px; text-align: right; }
  .btn-editar-ing {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.85rem;
    padding: 3px 8px;
    border-radius: 6px;
    color: var(--marron-claro);
    transition: background 0.15s;
  }
  .btn-editar-ing:hover { background: #f0e4d8; }
  .btn-del { background: none; border: none; color: #e8a598; cursor: pointer; font-size: 1.1rem; padding: 2px 6px; border-radius: 6px; transition: background 0.15s; }
  .btn-del:hover { background: #fce8e4; color: var(--rosa-oscuro); }

  /* Panel de edición (expandible) */
  .ing-row-edit {
    display: none;
    padding: 10px 14px 14px;
    border-top: 1px solid #f0e4d8;
    gap: 10px;
    flex-wrap: wrap;
    align-items: flex-end;
  }
  .ing-detalle-row.editando .ing-row-edit { display: flex; }
  .ing-row-edit label { font-size: 0.72rem; color: var(--gris); text-transform: uppercase; letter-spacing: 0.04em; display: block; margin-bottom: 3px; }
  .ing-row-edit select,
  .ing-row-edit input {
    border: 1.5px solid #e8d8cc;
    border-radius: 8px;
    padding: 6px 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.88rem;
    background: var(--crema);
    color: var(--texto);
    transition: border-color 0.2s;
  }
  .ing-row-edit select:focus,
  .ing-row-edit input:focus { outline: none; border-color: var(--rosa); background: var(--blanco); }
  .ing-row-edit select { min-width: 160px; }
  .ing-row-edit input { width: 100px; }
  .btn-save-ing {
    background: var(--marron);
    color: var(--crema);
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    transition: background 0.2s;
  }
  .btn-save-ing:hover { background: var(--marron-claro); }
  .btn-cancel-ing {
    background: none;
    border: 1px solid #e8d8cc;
    color: var(--gris);
    border-radius: 8px;
    padding: 7px 12px;
    cursor: pointer;
    font-size: 0.82rem;
    font-family: 'DM Sans', sans-serif;
    transition: all 0.2s;
  }
  .btn-cancel-ing:hover { border-color: var(--rosa); color: var(--rosa-oscuro); }

  /* AGREGAR INGREDIENTE */
  .add-ing-form {
    background: var(--crema);
    border-radius: 12px;
    padding: 16px;
    margin-top: 16px;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: flex-end;
  }
  .add-ing-form label { font-size: 0.78rem; color: var(--gris); display: block; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
  .add-ing-form select, .add-ing-form input {
    border: 1.5px solid #e8d8cc;
    border-radius: 8px;
    padding: 8px 12px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    background: var(--blanco);
    color: var(--texto);
  }
  .add-ing-form select:focus, .add-ing-form input:focus { outline: none; border-color: var(--rosa); }
  .add-ing-form select { min-width: 160px; }
  .add-ing-form input { width: 100px; }

  /* BOTONES */
  .btn-primary {
    background: var(--marron);
    color: var(--crema);
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    cursor: pointer;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    transition: background 0.2s;
  }
  .btn-primary:hover { background: var(--marron-claro); }
  .btn-secondary {
    background: var(--blanco);
    color: var(--marron);
    border: 1.5px solid var(--rosa);
    border-radius: 10px;
    padding: 10px 20px;
    cursor: pointer;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    transition: all 0.2s;
  }
  .btn-secondary:hover { background: var(--crema); }

  /* CONFIGURACION RECETA */
  .config-receta {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
    padding: 16px;
    background: var(--crema);
    border-radius: 12px;
    align-items: flex-end;
  }
  .config-receta label { font-size: 0.78rem; color: var(--gris); display: block; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
  .config-receta input {
    border: 1.5px solid #e8d8cc;
    border-radius: 8px;
    padding: 8px 12px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    background: var(--blanco);
    color: var(--texto);
    width: 120px;
  }
  .config-receta input:focus { outline: none; border-color: var(--rosa); }

  /* NUEVA RECETA FORM */
  .nueva-receta-form {
    background: var(--blanco);
    border-radius: 16px;
    padding: 20px;
    box-shadow: var(--sombra);
    margin-bottom: 20px;
    display: flex;
    gap: 12px;
    align-items: flex-end;
    flex-wrap: wrap;
  }
  .nueva-receta-form label { font-size: 0.78rem; color: var(--gris); display: block; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
  .nueva-receta-form input {
    border: 1.5px solid #e8d8cc;
    border-radius: 8px;
    padding: 8px 12px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    background: var(--crema);
    color: var(--texto);
  }
  .nueva-receta-form input:focus { outline: none; border-color: var(--rosa); background: var(--blanco); }

  /* TOAST */
  .toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: var(--verde);
    color: white;
    padding: 12px 20px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 0.88rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.3s;
    z-index: 999;
  }
  .toast.show { opacity: 1; transform: translateY(0); }

  /* SEARCH */
  .search-box {
    width: 100%;
    border: 1.5px solid #e8d8cc;
    border-radius: 12px;
    padding: 10px 16px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.95rem;
    background: var(--blanco);
    color: var(--texto);
    margin-bottom: 16px;
  }
  .search-box:focus { outline: none; border-color: var(--rosa); }

  /* LOADING */
  .loading { text-align: center; padding: 40px; color: var(--gris); font-style: italic; }

  /* RECETA SEARCH */
  .recetas-search {
    width: 100%;
    border: 1.5px solid #e8d8cc;
    border-radius: 12px;
    padding: 10px 16px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.95rem;
    background: var(--blanco);
    color: var(--texto);
    margin-bottom: 16px;
    transition: border-color 0.2s;
  }
  .recetas-search:focus { outline: none; border-color: var(--rosa); }

  /* BOTÓN DUPLICAR */
  .btn-duplicar {
    background: var(--crema);
    border: 1.5px solid #e8d8cc;
    color: var(--marron-claro);
    border-radius: 8px;
    padding: 5px 12px;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .btn-duplicar:hover { background: #f0e4d8; border-color: var(--rosa); color: var(--marron); }

  /* EDIT INLINE NOMBRE */
  .edit-nombre-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
  }
  .input-nombre-receta {
    font-family: 'Playfair Display', serif;
    font-size: 1.5rem;
    color: var(--marron);
    border: 1.5px solid transparent;
    border-radius: 8px;
    padding: 2px 8px;
    background: transparent;
    width: 100%;
    transition: border-color 0.2s, background 0.2s;
  }
  .input-nombre-receta:focus { outline: none; border-color: var(--rosa); background: var(--blanco); }
  .btn-save-nombre {
    background: var(--verde);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 5px 12px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    display: none;
    transition: background 0.2s;
  }
  .btn-save-nombre:hover { background: #5e8462; }

  /* NOTAS EN DETALLE */
  .notas-detalle {
    margin-bottom: 16px;
  }
  .notas-detalle label {
    font-size: 0.78rem;
    color: var(--gris);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: 6px;
  }
  .notas-detalle textarea {
    width: 100%;
    border: 1.5px solid #e8d8cc;
    border-radius: 10px;
    padding: 10px 14px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    background: var(--crema);
    color: var(--texto);
    resize: vertical;
    min-height: 60px;
    transition: border-color 0.2s, background 0.2s;
  }
  .notas-detalle textarea:focus { outline: none; border-color: var(--rosa); background: var(--blanco); }

  /* MARGEN EDITABLE */
  .margen-tag {
    background: var(--amarillo);
    color: var(--marron);
    border-radius: 20px;
    padding: 3px 10px;
    font-size: 0.78rem;
    font-weight: 700;
    position: absolute;
    top: 16px;
    right: 16px;
  }

  /* USUARIOS (solo admin) */
  .usuarios-section { margin-top: 32px; }
  .usuario-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--blanco);
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(92,61,46,0.06);
    margin-bottom: 8px;
  }
  .usuario-row .u-nombre { flex: 1; font-weight: 500; }
  .usuario-row .u-rol { font-size: 0.78rem; color: var(--gris); background: var(--crema); padding: 2px 10px; border-radius: 20px; }

  @media (max-width: 600px) {
    header h1 { font-size: 1.1rem; }
    .recetas-grid { grid-template-columns: 1fr; }
    .ing-row { flex-wrap: wrap; }
  }
</style>
</head>
<body>

<!-- PANTALLA DE LOGIN -->
<div id="login-screen">
  <div class="login-box">
    <div class="login-logo">
      <img src="/static/logo.png" alt="Roxi Pastelería" style="width:180px;margin-bottom:10px;"/>
      <span>Sistema de costeo</span>
    </div>
    <div class="login-field">
      <label>Usuario</label>
      <input type="text" id="login-usuario" placeholder="Tu usuario" autocomplete="username"
        onkeydown="if(event.key==='Enter') document.getElementById('login-pass').focus()"/>
    </div>
    <div class="login-field">
      <label>Contraseña</label>
      <input type="password" id="login-pass" placeholder="Tu contraseña" autocomplete="current-password"
        onkeydown="if(event.key==='Enter') hacerLogin()"/>
    </div>
    <button class="btn-login" onclick="hacerLogin()">Ingresar</button>
    <div class="login-error" id="login-error">Usuario o contraseña incorrectos</div>
  </div>
</div>

<!-- APP PRINCIPAL -->
<div id="app-screen">
  <header>
    <div style="display:flex;align-items:center;gap:14px;">
      <img src="/static/logo.png" alt="Roxi Pastelería" style="height:44px;border-radius:8px;"/>
      <div>
        <h1>Roxi Pastelería</h1>
        <span>Sistema de costeo</span>
      </div>
    </div>
    <div class="header-user">
      <span class="usuario-badge" id="usuario-badge"></span>
      <button class="btn-logout" onclick="cerrarSesion()">Salir</button>
    </div>
  </header>

  <nav id="nav-bar">
    <button class="active" onclick="showTab('resumen')">📊 Resumen</button>
    <button onclick="showTab('ingredientes')">🥚 Ingredientes</button>
    <button onclick="showTab('recetas')">📋 Recetas</button>
  </nav>

  <main id="app">
    <div class="loading">Cargando...</div>
  </main>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '';
let ingredientes = [];
let recetas = [];
let tabActual = 'resumen';
let recetaDetalle = null;
let clientes = [];
let presupuestos = [];
let presupuestoDetalle = null;
let usuarioActual = null;
let tokenActual = null;

// ── AUTH ──
async function hacerLogin() {
  const usuario = document.getElementById('login-usuario').value.trim();
  const password = document.getElementById('login-pass').value;
  if (!usuario || !password) return;

  const r = await fetch('/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ usuario, password })
  });
  const data = await r.json();

  if (!r.ok || data.detail) {
    document.getElementById('login-error').style.display = 'block';
    return;
  }

  tokenActual = data.token;
  usuarioActual = data.usuario;
  sessionStorage.setItem('token', tokenActual);
  sessionStorage.setItem('usuario', JSON.stringify(usuarioActual));
  mostrarApp();
}

function cerrarSesion() {
  sessionStorage.removeItem('token');
  sessionStorage.removeItem('usuario');
  tokenActual = null;
  usuarioActual = null;
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app-screen').style.display = 'none';
  document.getElementById('login-pass').value = '';
  document.getElementById('login-error').style.display = 'none';
}

async function mostrarApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'block';
  document.getElementById('usuario-badge').textContent = usuarioActual.nombre + (usuarioActual.rol === 'admin' ? ' (admin)' : '');

  // Agregar tabs extra según rol
  const nav = document.getElementById('nav-bar');
  if (!document.getElementById('btn-tab-clientes')) {
    const bc = document.createElement('button');
    bc.id = 'btn-tab-clientes';
    bc.textContent = '👥 Clientes';
    bc.onclick = () => showTab('clientes');
    nav.appendChild(bc);
  }
  if (!document.getElementById('btn-tab-presupuestos')) {
    const bp = document.createElement('button');
    bp.id = 'btn-tab-presupuestos';
    bp.textContent = '📄 Presupuestos';
    bp.onclick = () => showTab('presupuestos');
    nav.appendChild(bp);
  }
  if (usuarioActual.rol === 'admin') {
    if (!document.getElementById('btn-tab-usuarios')) {
      const btn = document.createElement('button');
      btn.id = 'btn-tab-usuarios';
      btn.textContent = '👤 Usuarios';
      btn.onclick = () => showTab('usuarios');
      nav.appendChild(btn);
    }
  }

  await cargarDatos();
  render();
}

// Verificar sesión guardada al cargar
window.addEventListener('load', () => {
  const token = sessionStorage.getItem('token');
  const usuario = sessionStorage.getItem('usuario');
  if (token && usuario) {
    tokenActual = token;
    usuarioActual = JSON.parse(usuario);
    mostrarApp();
  }
});

// ── HELPERS HTTP (con token) ──
function fmt(n) {
  return '$' + Math.round(n).toLocaleString('es-AR');
}

function toast(msg, color = '#7a9e7e') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = color;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function headers() {
  return {'Content-Type': 'application/json', 'Authorization': tokenActual || ''};
}

async function safeJson(r) {
  // Algunos endpoints devuelven 204 sin body — no intentar parsear
  if (r.status === 204 || r.headers.get('content-length') === '0') return null;
  try { return await r.json(); } catch(e) { return null; }
}

async function get(url) {
  const r = await fetch(API + url, { headers: headers() });
  if (r.status === 401) { cerrarSesion(); return {}; }
  return safeJson(r);
}
async function put(url, body) {
  const r = await fetch(API + url, { method: 'PUT', headers: headers(), body: JSON.stringify(body) });
  if (r.status === 401) { cerrarSesion(); return {}; }
  return safeJson(r);
}
async function post(url, body) {
  const r = await fetch(API + url, { method: 'POST', headers: headers(), body: JSON.stringify(body) });
  if (r.status === 401) { cerrarSesion(); return {}; }
  return safeJson(r);
}
async function del(url) {
  const r = await fetch(API + url, { method: 'DELETE', headers: headers() });
  if (r.status === 401) { cerrarSesion(); return null; }
  return safeJson(r);
}

async function cargarDatos() {
  [ingredientes, recetas, clientes, presupuestos] = await Promise.all([get('/ingredientes'), get('/recetas'), get('/clientes'), get('/presupuestos')]);
}

function showTab(tab) {
  tabActual = tab;
  recetaDetalle = null;
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  const tabs = ['resumen','ingredientes','recetas','clientes','presupuestos','usuarios'];
  document.querySelectorAll('nav button').forEach((b,i) => {
    if (tabs[i] === tab) b.classList.add('active');
  });
  render();
}

async function render() {
  const app = document.getElementById('app');
  if (tabActual === 'resumen') renderResumen(app);
  else if (tabActual === 'ingredientes') renderIngredientes(app);
  else if (tabActual === 'recetas') {
    if (recetaDetalle) renderDetalle(app);
    else renderRecetas(app);
  }
  else if (tabActual === 'usuarios') renderUsuarios(app);
  else if (tabActual === 'clientes') renderClientes(app);
  else if (tabActual === 'presupuestos') {
    if (presupuestoDetalle) renderPresupuestoDetalle(app);
    else renderPresupuestos(app);
  }
}

// ── RESUMEN ──
async function renderResumen(app) {
  const data = await get('/resumen');
  app.innerHTML = `
    <div class="stats">
      <div class="stat"><div class="num">${data.total_ingredientes}</div><div class="lbl">Ingredientes</div></div>
      <div class="stat"><div class="num">${data.total_recetas}</div><div class="lbl">Recetas</div></div>
    </div>
    <div class="sec-title">Todos los productos</div>
    <div style="display:flex;flex-direction:column;gap:10px;">
      ${data.productos.map(p => `
        <div class="card" style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;cursor:pointer;" onclick="verReceta('${p.nombre}')">
          <div>
            <div style="font-family:'Playfair Display',serif;font-weight:600;font-size:1rem;color:var(--marron)">${p.nombre}</div>
            <div style="font-size:0.8rem;color:var(--gris);margin-top:3px">Costo: ${fmt(p.costo)}</div>
          </div>
          <div style="font-family:'Playfair Display',serif;font-size:1.3rem;font-weight:700;color:var(--marron)">${fmt(p.precio_final)}</div>
        </div>
      `).join('')}
    </div>
  `;
}

async function verReceta(nombre) {
  const r = recetas.find(x => x.nombre === nombre);
  if (r) {
    recetaDetalle = r;
    tabActual = 'recetas';
    document.querySelectorAll('nav button').forEach((b,i) => b.classList.toggle('active', i === 2));
    render();
  }
}

// ── INGREDIENTES ──
let ingEditandoId = null;

function renderIngredientes(app) {
  app.innerHTML = `
    <div class="sec-title">Ingredientes</div>
    <div class="nueva-receta-form" id="form-ing">
      <div><label>Nombre</label><input type="text" id="ing-nombre" placeholder="Ej: Manteca"/></div>
      <div>
        <label>Unidad</label>
        <select id="ing-unidad" style="border:1.5px solid #e8d8cc;border-radius:8px;padding:8px 12px;font-family:'DM Sans',sans-serif;font-size:0.9rem;background:var(--crema);color:var(--texto);">
          <option value="KG">KG (por kilo)</option>
          <option value="LT">LT (por litro)</option>
          <option value="UN">UN (por unidad)</option>
        </select>
      </div>
      <div><label>Precio ($)</label><input type="number" id="ing-precio" placeholder="Ej: 2200"/></div>
      <button class="btn-primary" onclick="guardarIngrediente()">+ Agregar</button>
      <button class="btn-secondary" id="btn-cancelar-ing" style="display:none" onclick="cancelarEdicion()">Cancelar</button>
    </div>
    <input class="search-box" type="text" placeholder="🔍 Buscar ingrediente..." oninput="filtrarIng(this.value)"/>
    <div class="ing-list" id="ing-list">
      ${renderIngList(ingredientes)}
    </div>
  `;
}

function renderIngList(lista) {
  return lista.map(ing => `
    <div class="ing-row" id="ing-row-${ing.id}">
      <span class="ing-nombre">${ing.nombre}</span>
      <span class="ing-unidad">${ing.unidad}</span>
      <div class="ing-precio">
        <span>$</span>
        <input class="precio-input" type="number" value="${ing.precio}" id="precio-${ing.id}"
          onkeydown="if(event.key==='Enter') guardarPrecio(${ing.id})"/>
        <button class="btn-save" onclick="guardarPrecio(${ing.id})" title="Guardar precio">✓</button>
      </div>
      <button onclick="editarIngrediente(${ing.id})" title="Editar"
        style="background:var(--crema);border:none;border-radius:8px;padding:5px 10px;cursor:pointer;color:var(--marron-claro);font-size:0.9rem;">✏️</button>
      <button onclick="eliminarIngrediente(${ing.id}, '${ing.nombre}')" title="Eliminar"
        style="background:none;border:none;cursor:pointer;color:var(--rosa);font-size:1rem;padding:5px 8px;border-radius:6px;">🗑️</button>
    </div>
  `).join('');
}

function filtrarIng(q) {
  const lista = ingredientes.filter(i => i.nombre.toLowerCase().includes(q.toLowerCase()));
  document.getElementById('ing-list').innerHTML = renderIngList(lista);
}

function editarIngrediente(id) {
  const ing = ingredientes.find(i => i.id === id);
  if (!ing) return;
  ingEditandoId = id;
  document.getElementById('ing-nombre').value = ing.nombre;
  document.getElementById('ing-unidad').value = ing.unidad;
  document.getElementById('ing-precio').value = ing.precio;
  document.querySelector('#form-ing button.btn-primary').textContent = '💾 Guardar cambios';
  document.getElementById('btn-cancelar-ing').style.display = '';
  document.getElementById('ing-nombre').focus();
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function cancelarEdicion() {
  ingEditandoId = null;
  document.getElementById('ing-nombre').value = '';
  document.getElementById('ing-precio').value = '';
  document.querySelector('#form-ing button.btn-primary').textContent = '+ Agregar';
  document.getElementById('btn-cancelar-ing').style.display = 'none';
}

async function guardarIngrediente() {
  const nombre = document.getElementById('ing-nombre').value.trim();
  const unidad = document.getElementById('ing-unidad').value;
  const precio = parseFloat(document.getElementById('ing-precio').value);
  if (!nombre) { toast('Ingresá un nombre', '#e8a598'); return; }
  if (isNaN(precio) || precio < 0) { toast('Precio inválido', '#e8a598'); return; }

  if (ingEditandoId) {
    const r = await put(`/ingredientes/${ingEditandoId}`, { nombre, unidad, precio });
    if (r.detail) { toast(r.detail, '#e8a598'); return; }
    const idx = ingredientes.findIndex(i => i.id === ingEditandoId);
    if (idx >= 0) ingredientes[idx] = r;
    cancelarEdicion();
    recetas = await get('/recetas');
    document.getElementById('ing-list').innerHTML = renderIngList(ingredientes);
    toast('✓ Ingrediente actualizado');
  } else {
    const r = await post('/ingredientes', { nombre, unidad, precio });
    if (r.detail) { toast(r.detail, '#e8a598'); return; }
    ingredientes.push(r);
    ingredientes.sort((a,b) => a.nombre.localeCompare(b.nombre));
    cancelarEdicion();
    document.getElementById('ing-list').innerHTML = renderIngList(ingredientes);
    toast('✓ Ingrediente creado');
  }
}

async function guardarPrecio(id) {
  const input = document.getElementById(`precio-${id}`);
  const precio = parseFloat(input.value);
  if (isNaN(precio) || precio < 0) { toast('Precio inválido', '#e8a598'); return; }
  await put(`/ingredientes/${id}`, { precio });
  const idx = ingredientes.findIndex(i => i.id === id);
  if (idx >= 0) ingredientes[idx].precio = precio;
  recetas = await get('/recetas');
  toast('✓ Precio actualizado');
}

async function eliminarIngrediente(id, nombre) {
  if (!confirm(`¿Eliminar "${nombre}"?\n\nSi está siendo usado en alguna receta no se podrá eliminar.`)) return;
  const r = await del(`/ingredientes/${id}`);
  if (r.detail) { toast(r.detail, '#e8a598'); return; }
  ingredientes = ingredientes.filter(i => i.id !== id);
  document.getElementById('ing-list').innerHTML = renderIngList(ingredientes);
  toast('Ingrediente eliminado', '#c97b6e');
}

// ── RECETAS ──
function renderRecetasGrid(lista) {
  if (!lista.length) return '<div class="loading">No se encontraron recetas</div>';
  return lista.map(r => `
    <div class="receta-card" onclick="abrirDetalle(${r.id})">
      <span class="margen-tag">x${r.margen}</span>
      <h3>${r.nombre}</h3>
      ${r.notas ? `<div class="notas">${r.notas}</div>` : ''}
      <div class="receta-nums">
        <div class="receta-num-row"><span class="lbl">Ingredientes</span><span class="val">${fmt(r.costo_ingredientes)}</span></div>
        <div class="receta-num-row"><span class="lbl">Gastos extra</span><span class="val">${fmt(r.gastos_extra)}</span></div>
        <div class="receta-num-row"><span class="lbl">Costo total</span><span class="val">${fmt(r.costo_total)}</span></div>
      </div>
      <div class="precio-final-badge">
        <span class="lbl">Precio sugerido</span>
        <span class="val">${fmt(r.precio_final)}</span>
      </div>
    </div>
  `).join('');
}

function filtrarRecetas(q) {
  const lista = recetas.filter(r => r.nombre.toLowerCase().includes(q.toLowerCase()));
  document.getElementById('recetas-grid').innerHTML = renderRecetasGrid(lista);
}

function renderRecetas(app) {
  app.innerHTML = `
    <div class="sec-title">Recetas</div>
    <div class="nueva-receta-form">
      <div><label>Nombre del producto</label><input type="text" id="nueva-nombre" placeholder="Ej: Torta Chocolate"/></div>
      <div><label>Gastos extra ($)</label><input type="number" id="nueva-gastos" value="300"/></div>
      <div><label>Margen (x)</label><input type="number" id="nueva-margen" value="3" step="0.1"/></div>
      <button class="btn-primary" onclick="crearReceta()">+ Nueva receta</button>
    </div>
    <input class="recetas-search" type="text" placeholder="🔍 Buscar receta..." oninput="filtrarRecetas(this.value)"/>
    <div class="recetas-grid" id="recetas-grid">
      ${renderRecetasGrid(recetas)}
    </div>
  `;
}

async function crearReceta() {
  const nombre = document.getElementById('nueva-nombre').value.trim();
  const gastos = parseFloat(document.getElementById('nueva-gastos').value) || 300;
  const margen = parseFloat(document.getElementById('nueva-margen').value) || 3;
  if (!nombre) { toast('Ingresá un nombre', '#e8a598'); return; }
  const r = await post('/recetas', { nombre, gastos_extra: gastos, margen });
  if (r.detail) { toast(r.detail, '#e8a598'); return; }
  recetas = await get('/recetas');
  recetaDetalle = r;
  render();
  toast('✓ Receta creada');
}

async function abrirDetalle(id) {
  const data = await get(`/recetas/${id}`);
  recetaDetalle = data;
  render();
}

// ── DETALLE ──
async function renderDetalle(app) {
  const r = recetaDetalle;
  app.innerHTML = `
    <div class="detalle-header">
      <button class="btn-back" onclick="volverRecetas()">← Volver</button>
      <div class="edit-nombre-wrap">
        <input class="input-nombre-receta" id="input-nombre-receta" type="text" value="${r.nombre}"
          oninput="document.getElementById('btn-save-nombre').style.display='inline-block'"
          onkeydown="if(event.key==='Enter') guardarNombreReceta(${r.id})"/>
        <button class="btn-save-nombre" id="btn-save-nombre" onclick="guardarNombreReceta(${r.id})">✓ Guardar</button>
      </div>
      <div style="display:flex;gap:8px;margin-left:auto;">
        <button class="btn-duplicar" onclick="duplicarReceta(${r.id}, '${r.nombre.replace(/'/g,"\\'")}')">📋 Duplicar</button>
        <button onclick="eliminarReceta(${r.id}, '${r.nombre.replace(/'/g,"\\'")}' )"
          style="background:#fce8e4;border:none;border-radius:10px;padding:8px 16px;cursor:pointer;color:var(--rosa-oscuro);font-weight:600;font-size:0.88rem;transition:background 0.2s;"
          onmouseover="this.style.background='#f8d0c8'" onmouseout="this.style.background='#fce8e4'">
          🗑️ Eliminar
        </button>
      </div>
    </div>
    <div class="notas-detalle">
      <label>📝 Notas / descripción</label>
      <textarea id="cfg-notas" placeholder="Ej: Para 12 porciones, guardar en heladera...">${r.notas || ''}</textarea>
    </div>
    <div class="config-receta">
      <div><label>Gastos extra ($)</label><input type="number" id="cfg-gastos" value="${r.gastos_extra}"/></div>
      <div><label>Margen (x)</label><input type="number" id="cfg-margen" value="${r.margen}" step="0.1"/></div>
      <button class="btn-primary" onclick="guardarConfig(${r.id})">Guardar</button>
    </div>
    <div class="detalle-resumen">
      <div class="detalle-stat"><div class="num">${fmt(r.costo_ingredientes)}</div><div class="lbl">Ingredientes</div></div>
      <div class="detalle-stat"><div class="num">${fmt(r.gastos_extra)}</div><div class="lbl">Gastos extra</div></div>
      <div class="detalle-stat"><div class="num">${fmt(r.costo_total)}</div><div class="lbl">Costo total</div></div>
      <div class="detalle-stat" style="background:var(--marron);color:var(--crema)">
        <div class="num" style="color:var(--amarillo)">${fmt(r.precio_final)}</div>
        <div class="lbl" style="color:rgba(255,255,255,0.7)">Precio final</div>
      </div>
    </div>
    <div class="sec-title">Ingredientes</div>
    <div id="ing-detalle">
      ${renderIngDetalle(r.ingredientes)}
    </div>
    <div class="add-ing-form">
      <div>
        <label>Ingrediente</label>
        <select id="add-ing-sel">
          ${ingredientes.map(i => `<option value="${i.id}">${i.nombre} (${i.unidad})</option>`).join('')}
        </select>
      </div>
      <div>
        <label>Cantidad (g / ml / unid)</label>
        <input type="number" id="add-ing-cant" placeholder="Ej: 200"/>
      </div>
      <button class="btn-primary" onclick="agregarIngrediente(${r.id})">+ Agregar</button>
    </div>
  `;
}

function renderIngDetalle(lista) {
  if (!lista.length) return '<div style="color:var(--gris);font-style:italic;padding:12px">Sin ingredientes aún</div>';
  return lista.map(i => `
    <div class="ing-detalle-row" id="ing-edit-row-${i.id}">
      <div class="ing-row-vista">
        <span class="nombre">${i.nombre}</span>
        <span class="cant">${i.cantidad} ${i.unidad === 'UN' ? 'un.' : 'g/ml'}</span>
        <span class="costo">${fmt(i.costo_real)}</span>
        <button class="btn-editar-ing" onclick="toggleEditIng(${i.id})" title="Editar">✏️</button>
        <button class="btn-del" onclick="quitarIngrediente(${recetaDetalle.id}, ${i.id})" title="Quitar">✕</button>
      </div>
      <div class="ing-row-edit">
        <div>
          <label>Ingrediente</label>
          <select id="edit-ing-sel-${i.id}">
            ${ingredientes.map(ing => `<option value="${ing.id}" ${ing.id === i.ingrediente_id ? 'selected' : ''}>${ing.nombre} (${ing.unidad})</option>`).join('')}
          </select>
        </div>
        <div>
          <label>Cantidad</label>
          <input type="number" id="edit-ing-cant-${i.id}" value="${i.cantidad}" min="0" step="any"/>
        </div>
        <div>
          <label>Precio del ing. ($)</label>
          <input type="number" id="edit-ing-precio-${i.id}" value="${i.precio_unitario || ''}" placeholder="Precio/kg o unid"/>
        </div>
        <button class="btn-save-ing" onclick="guardarEdicionIng(${recetaDetalle.id}, ${i.id})">✓ Guardar</button>
        <button class="btn-cancel-ing" onclick="toggleEditIng(${i.id})">Cancelar</button>
      </div>
    </div>
  `).join('');
}

function toggleEditIng(riId) {
  const row = document.getElementById(`ing-edit-row-${riId}`);
  if (!row) return;
  row.classList.toggle('editando');
}

async function guardarEdicionIng(recetaId, riId) {
  const ing_id = parseInt(document.getElementById(`edit-ing-sel-${riId}`).value);
  const cantidad = parseFloat(document.getElementById(`edit-ing-cant-${riId}`).value);
  const precioInput = document.getElementById(`edit-ing-precio-${riId}`).value.trim();

  if (isNaN(cantidad) || cantidad <= 0) { toast('Cantidad inválida', '#e8a598'); return; }

  try {
    // Actualizar precio base solo si se completó Y tenemos el ingrediente completo
    if (precioInput !== '') {
      const precio = parseFloat(precioInput);
      if (!isNaN(precio) && precio > 0) {
        const ingBase = ingredientes.find(i => i.id === ing_id);
        if (ingBase) {
          await put(`/ingredientes/${ing_id}`, {
            nombre: ingBase.nombre,
            unidad: ingBase.unidad,
            precio
          });
          ingBase.precio = precio;
        }
      }
    }

    // Quitar el anterior y agregar el nuevo
    await del(`/recetas/${recetaId}/ingredientes/${riId}`);
    const data = await post(`/recetas/${recetaId}/ingredientes`, { ingrediente_id: ing_id, cantidad });
    if (data && data.detail) { toast(data.detail, '#e8a598'); return; }

    // Si la respuesta no trae ingredientes, recargar desde API
    let detalle = data;
    if (!detalle || !detalle.ingredientes) {
      detalle = await get(`/recetas/${recetaId}`);
    }
    recetaDetalle = detalle;
    recetas = await get('/recetas');
    const ingDiv = document.getElementById('ing-detalle');
    if (ingDiv) ingDiv.innerHTML = renderIngDetalle(recetaDetalle.ingredientes || []);
    actualizarResumenDetalle(recetaDetalle);
    toast('✓ Ingrediente actualizado');
  } catch(e) {
    console.error('guardarEdicionIng error:', e);
    toast('Error al actualizar ingrediente', '#e8a598');
  }
}

async function guardarConfig(recetaId) {
  const gastos = parseFloat(document.getElementById('cfg-gastos').value);
  const margen = parseFloat(document.getElementById('cfg-margen').value);
  const notas = document.getElementById('cfg-notas').value.trim();
  const data = await put(`/recetas/${recetaId}`, { gastos_extra: gastos, margen, notas });
  recetaDetalle = data;
  recetas = await get('/recetas');
  render();
  toast('✓ Configuración guardada');
}

async function agregarIngrediente(recetaId) {
  const selEl = document.getElementById('add-ing-sel');
  const cantEl = document.getElementById('add-ing-cant');
  if (!selEl || !cantEl) { toast('Error: formulario no encontrado', '#e8a598'); return; }

  const ing_id = parseInt(selEl.value);
  const cantidad = parseFloat(cantEl.value);
  if (isNaN(cantidad) || cantidad <= 0) { toast('Ingresá una cantidad válida', '#e8a598'); return; }

  const btnAgregar = document.querySelector('.add-ing-form .btn-primary');
  if (btnAgregar) { btnAgregar.disabled = true; btnAgregar.textContent = 'Agregando...'; }

  try {
    let data = await post(`/recetas/${recetaId}/ingredientes`, { ingrediente_id: ing_id, cantidad });
    if (data && data.detail) { toast(data.detail, '#e8a598'); return; }
    // Si la respuesta no trae ingredientes, recargar el detalle desde la API
    if (!data || !data.ingredientes) {
      data = await get(`/recetas/${recetaId}`);
    }
    recetaDetalle = data;
    recetas = await get('/recetas');
    const ingDiv = document.getElementById('ing-detalle');
    if (ingDiv) ingDiv.innerHTML = renderIngDetalle(recetaDetalle.ingredientes || []);
    actualizarResumenDetalle(recetaDetalle);
    cantEl.value = '';
    toast('✓ Ingrediente agregado');
  } catch(e) {
    console.error('agregarIngrediente error:', e);
    toast('Error al agregar ingrediente', '#e8a598');
  } finally {
    if (btnAgregar) { btnAgregar.disabled = false; btnAgregar.textContent = '+ Agregar'; }
  }
}

async function quitarIngrediente(recetaId, riId) {
  if (!confirm('¿Quitar este ingrediente?')) return;
  const rowEl = document.getElementById(`ing-edit-row-${riId}`);
  if (rowEl) rowEl.style.opacity = '0.4';

  try {
    let data = await del(`/recetas/${recetaId}/ingredientes/${riId}`);
    if (data && data.detail) { toast(data.detail, '#e8a598'); if (rowEl) rowEl.style.opacity = '1'; return; }
    // Si el DELETE devuelve null (204) o no trae ingredientes, recargar desde API
    if (!data || !data.ingredientes) {
      data = await get(`/recetas/${recetaId}`);
    }
    recetaDetalle = data;
    recetas = await get('/recetas');
    const ingDiv = document.getElementById('ing-detalle');
    if (ingDiv) ingDiv.innerHTML = renderIngDetalle(recetaDetalle.ingredientes || []);
    actualizarResumenDetalle(recetaDetalle);
    toast('Ingrediente quitado', '#c97b6e');
  } catch(e) {
    console.error('quitarIngrediente error:', e);
    toast('Error al quitar ingrediente', '#e8a598');
    if (rowEl) rowEl.style.opacity = '1';
  }
}

function actualizarResumenDetalle(r) {
  // Actualiza los números del resumen sin re-renderizar toda la pantalla
  const stats = document.querySelectorAll('.detalle-stat .num');
  if (stats.length >= 4) {
    stats[0].textContent = fmt(r.costo_ingredientes);
    stats[1].textContent = fmt(r.gastos_extra);
    stats[2].textContent = fmt(r.costo_total);
    stats[3].textContent = fmt(r.precio_final);
  }
}

async function guardarNombreReceta(recetaId) {
  const nombre = document.getElementById('input-nombre-receta').value.trim();
  if (!nombre) { toast('El nombre no puede estar vacío', '#e8a598'); return; }
  const data = await put(`/recetas/${recetaId}`, { nombre });
  if (data.detail) { toast(data.detail, '#e8a598'); return; }
  recetaDetalle = { ...recetaDetalle, nombre };
  recetas = await get('/recetas');
  document.getElementById('btn-save-nombre').style.display = 'none';
  toast('✓ Nombre actualizado');
}

async function duplicarReceta(id, nombre) {
  const nuevonombre = `${nombre} (copia)`;
  const original = recetaDetalle;
  // Crear nueva receta con los mismos parámetros
  const nueva = await post('/recetas', {
    nombre: nuevonombre,
    gastos_extra: original.gastos_extra,
    margen: original.margen,
    notas: original.notas || ''
  });
  if (nueva.detail) { toast(nueva.detail, '#e8a598'); return; }
  // Copiar ingredientes uno por uno
  for (const ing of (original.ingredientes || [])) {
    await post(`/recetas/${nueva.id}/ingredientes`, {
      ingrediente_id: ing.id,
      cantidad: ing.cantidad
    });
  }
  recetas = await get('/recetas');
  recetaDetalle = await get(`/recetas/${nueva.id}`);
  render();
  toast(`✓ Receta duplicada como "${nuevonombre}"`);
}

async function volverRecetas() {
  recetaDetalle = null;
  recetas = await get('/recetas');
  render();
}

async function eliminarReceta(id, nombre) {
  if (!confirm(`¿Eliminar la receta "${nombre}"?\n\nEsta acción no se puede deshacer.`)) return;
  await del(`/recetas/${id}`);
  recetaDetalle = null;
  recetas = await get('/recetas');
  tabActual = 'recetas';
  render();
  toast('Receta eliminada', '#c97b6e');
}

// ── USUARIOS (solo admin) ──
async function renderUsuarios(app) {
  const data = await get('/usuarios');
  if (data.detail) { app.innerHTML = '<div class="loading">Sin acceso</div>'; return; }
  app.innerHTML = `
    <div class="sec-title">Usuarios</div>
    <div class="nueva-receta-form">
      <div><label>Usuario</label><input type="text" id="nu-usuario" placeholder="Ej: maria"/></div>
      <div><label>Contraseña</label><input type="password" id="nu-pass" placeholder="Contraseña"/></div>
      <div><label>Nombre</label><input type="text" id="nu-nombre" placeholder="Ej: María García"/></div>
      <div>
        <label>Rol</label>
        <select id="nu-rol" style="border:1.5px solid #e8d8cc;border-radius:8px;padding:8px 12px;font-family:'DM Sans',sans-serif;font-size:0.9rem;background:var(--crema);color:var(--texto);">
          <option value="usuario">Usuario</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <button class="btn-primary" onclick="crearUsuario()">+ Crear usuario</button>
    </div>
    <div>
      ${data.map(u => `
        <div class="usuario-row">
          <span class="u-nombre">${u.nombre} <span style="color:var(--gris);font-size:0.85rem">(${u.usuario})</span></span>
          <span class="u-rol">${u.rol}</span>
          ${u.usuario !== 'admin' ? `<button onclick="eliminarUsuario(${u.id}, '${u.nombre}')"
            style="background:none;border:none;cursor:pointer;color:var(--rosa);font-size:1rem;padding:5px 8px;border-radius:6px;">🗑️</button>` : ''}
        </div>
      `).join('')}
    </div>
  `;
}

async function crearUsuario() {
  const usuario = document.getElementById('nu-usuario').value.trim();
  const password = document.getElementById('nu-pass').value;
  const nombre = document.getElementById('nu-nombre').value.trim();
  const rol = document.getElementById('nu-rol').value;
  if (!usuario || !password || !nombre) { toast('Completá todos los campos', '#e8a598'); return; }
  const r = await post('/usuarios', { usuario, password, nombre, rol });
  if (r.detail) { toast(r.detail, '#e8a598'); return; }
  toast('✓ Usuario creado');
  renderUsuarios(document.getElementById('app'));
}

async function eliminarUsuario(id, nombre) {
  if (!confirm(`¿Eliminar usuario "${nombre}"?`)) return;
  const r = await del(`/usuarios/${id}`);
  if (r.detail) { toast(r.detail, '#e8a598'); return; }
  toast('Usuario eliminado', '#c97b6e');
  renderUsuarios(document.getElementById('app'));
}

// ══════════════════════════════════════════
// CLIENTES
// ══════════════════════════════════════════

function renderClientes(app) {
  app.innerHTML = `
    <div class="sec-title">👥 Clientes</div>
    <div class="nueva-receta-form">
      <div><label>Nombre *</label><input type="text" id="cl-nombre" placeholder="Nombre del cliente"/></div>
      <div><label>Teléfono</label><input type="text" id="cl-tel" placeholder="Ej: 351-1234567"/></div>
      <div><label>Email</label><input type="text" id="cl-email" placeholder="cliente@mail.com"/></div>
      <button class="btn-primary" onclick="crearCliente()">+ Agregar cliente</button>
    </div>
    <div class="ing-list" id="cl-list">
      ${renderClienteList(clientes)}
    </div>
  `;
}

function renderClienteList(lista) {
  if (!lista.length) return '<div class="loading">Sin clientes aún</div>';
  return lista.map(cl => `
    <div class="ing-item" id="cl-item-${cl.id}">
      <div style="flex:1">
        <div style="font-weight:600">${cl.nombre}</div>
        <div style="font-size:0.82rem;color:var(--gris)">${[cl.telefono, cl.email].filter(Boolean).join(' · ') || 'Sin contacto'}</div>
      </div>
      <button onclick="abrirEditCliente(${cl.id})" style="background:none;border:none;cursor:pointer;color:var(--marron-claro);font-size:1rem;padding:5px 8px;">✏️</button>
      <button onclick="eliminarCliente(${cl.id}, '${cl.nombre.replace(/'/g,"\\'")}' )" style="background:none;border:none;cursor:pointer;color:var(--rosa);font-size:1rem;padding:5px 8px;">🗑️</button>
    </div>
  `).join('');
}

async function crearCliente() {
  const nombre = document.getElementById('cl-nombre').value.trim();
  if (!nombre) { toast('El nombre es obligatorio', '#e8a598'); return; }
  const tel = document.getElementById('cl-tel').value.trim();
  const email = document.getElementById('cl-email').value.trim();
  const r = await post('/clientes', { nombre, telefono: tel||null, email: email||null });
  if (r.detail) { toast(r.detail, '#e8a598'); return; }
  clientes = await get('/clientes');
  document.getElementById('cl-nombre').value = '';
  document.getElementById('cl-tel').value = '';
  document.getElementById('cl-email').value = '';
  document.getElementById('cl-list').innerHTML = renderClienteList(clientes);
  toast('✓ Cliente agregado');
}

function abrirEditCliente(id) {
  const cl = clientes.find(c => c.id === id);
  if (!cl) return;
  const item = document.getElementById(`cl-item-${id}`);
  item.innerHTML = `
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;width:100%">
      <input type="text" id="edit-cl-nombre-${id}" value="${cl.nombre}" style="flex:1;min-width:120px;border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;"/>
      <input type="text" id="edit-cl-tel-${id}" value="${cl.telefono||''}" placeholder="Teléfono" style="width:130px;border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;"/>
      <input type="text" id="edit-cl-email-${id}" value="${cl.email||''}" placeholder="Email" style="width:160px;border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;"/>
      <button onclick="guardarCliente(${id})" class="btn-primary" style="padding:7px 14px;">✓</button>
      <button onclick="renderClientes(document.getElementById('app'))" style="background:none;border:1px solid #e8d8cc;border-radius:8px;padding:7px 10px;cursor:pointer;font-family:'DM Sans',sans-serif;">✕</button>
    </div>
  `;
}

async function guardarCliente(id) {
  const nombre = document.getElementById(`edit-cl-nombre-${id}`).value.trim();
  const tel = document.getElementById(`edit-cl-tel-${id}`).value.trim();
  const email = document.getElementById(`edit-cl-email-${id}`).value.trim();
  if (!nombre) { toast('El nombre es obligatorio', '#e8a598'); return; }
  await put(`/clientes/${id}`, { nombre, telefono: tel||null, email: email||null });
  clientes = await get('/clientes');
  document.getElementById('cl-list').innerHTML = renderClienteList(clientes);
  toast('✓ Cliente actualizado');
}

async function eliminarCliente(id, nombre) {
  if (!confirm(`¿Eliminar cliente "${nombre}"?`)) return;
  await del(`/clientes/${id}`);
  clientes = await get('/clientes');
  document.getElementById('cl-list').innerHTML = renderClienteList(clientes);
  toast('Cliente eliminado', '#c97b6e');
}

// ══════════════════════════════════════════
// PRESUPUESTOS
// ══════════════════════════════════════════

const ESTADOS = { borrador: '📝 Borrador', enviado: '📤 Enviado', aceptado: '✅ Aceptado', rechazado: '❌ Rechazado' };
const ESTADO_COLOR = { borrador: '#fff8e6', enviado: '#e8f0fb', aceptado: '#edf7ee', rechazado: '#fce8e4' };
const ESTADO_TEXT = { borrador: '#7a6020', enviado: '#2a5090', aceptado: '#3a6e40', rechazado: '#c97b6e' };

function renderPresupuestos(app) {
  app.innerHTML = `
    <div class="sec-title">📄 Presupuestos</div>
    <div class="nueva-receta-form">
      <div><label>Título *</label><input type="text" id="pres-titulo" placeholder="Ej: Torta cumpleaños 15"/></div>
      <div>
        <label>Cliente</label>
        <select id="pres-cliente" style="border:1.5px solid #e8d8cc;border-radius:10px;padding:10px 14px;font-family:'DM Sans',sans-serif;background:var(--crema);width:100%;">
          <option value="">Sin cliente</option>
          ${clientes.map(cl => `<option value="${cl.id}">${cl.nombre}</option>`).join('')}
        </select>
      </div>
      <button class="btn-primary" onclick="crearPresupuesto()">+ Nuevo presupuesto</button>
    </div>
    <div class="recetas-grid" id="pres-grid">
      ${renderPresupuestosGrid(presupuestos)}
    </div>
  `;
}

function renderPresupuestosGrid(lista) {
  if (!lista.length) return '<div class="loading">Sin presupuestos aún</div>';
  return lista.map(p => `
    <div class="receta-card" onclick="abrirPresupuesto(${p.id})" style="cursor:pointer">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
        <h3 style="margin:0">${p.titulo}</h3>
        <span style="font-size:0.75rem;font-weight:600;padding:3px 10px;border-radius:20px;background:${ESTADO_COLOR[p.estado]||'#f5f5f5'};color:${ESTADO_TEXT[p.estado]||'#666'}">${ESTADOS[p.estado]||p.estado}</span>
      </div>
      ${p.cliente_nombre ? `<div style="font-size:0.83rem;color:var(--gris);margin-bottom:6px">👥 ${p.cliente_nombre}</div>` : ''}
      <div class="precio-final-badge"><span class="lbl">Total</span><span class="val">${fmt(p.total)}</span></div>
      <div style="font-size:0.75rem;color:var(--gris);margin-top:8px">${new Date(p.created_at).toLocaleDateString('es-AR')}</div>
    </div>
  `).join('');
}

async function crearPresupuesto() {
  const titulo = document.getElementById('pres-titulo').value.trim();
  if (!titulo) { toast('El título es obligatorio', '#e8a598'); return; }
  const cliente_id = document.getElementById('pres-cliente').value || null;
  const r = await post('/presupuestos', { titulo, cliente_id: cliente_id ? parseInt(cliente_id) : null });
  if (r.detail) { toast(r.detail, '#e8a598'); return; }
  presupuestoDetalle = r;
  presupuestos = await get('/presupuestos');
  render();
}

async function abrirPresupuesto(id) {
  presupuestoDetalle = await get(`/presupuestos/${id}`);
  render();
}

async function renderPresupuestoDetalle(app) {
  const p = presupuestoDetalle;
  app.innerHTML = `
    <div class="detalle-header">
      <button class="btn-back" onclick="volverPresupuestos()">← Volver</button>
      <div class="edit-nombre-wrap">
        <input class="input-nombre-receta" id="pres-titulo-input" type="text" value="${p.titulo}"
          oninput="document.getElementById('btn-save-pres-titulo').style.display='inline-block'"
          onkeydown="if(event.key==='Enter') guardarTituloPresupuesto(${p.id})"/>
        <button class="btn-save-nombre" id="btn-save-pres-titulo" onclick="guardarTituloPresupuesto(${p.id})">✓ Guardar</button>
      </div>
      <div style="display:flex;gap:8px;margin-left:auto;align-items:center">
        <select id="pres-estado-sel" onchange="cambiarEstadoPresupuesto(${p.id})"
          style="border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;background:${ESTADO_COLOR[p.estado]};color:${ESTADO_TEXT[p.estado]};font-weight:600;font-size:0.85rem;">
          ${Object.entries(ESTADOS).map(([k,v]) => `<option value="${k}" ${k===p.estado?'selected':''}>${v}</option>`).join('')}
        </select>
        <button onclick="imprimirPresupuesto()" style="background:var(--crema);border:1.5px solid #e8d8cc;border-radius:8px;padding:7px 14px;cursor:pointer;font-size:0.85rem;font-weight:600;font-family:'DM Sans',sans-serif;">🖨️ Imprimir</button>
        <button onclick="eliminarPresupuesto(${p.id})" style="background:#fce8e4;border:none;border-radius:8px;padding:7px 14px;cursor:pointer;color:var(--rosa-oscuro);font-weight:600;font-size:0.85rem;font-family:'DM Sans',sans-serif;">🗑️ Eliminar</button>
      </div>
    </div>

    <!-- Cliente -->
    <div style="background:var(--blanco);border-radius:14px;box-shadow:var(--sombra);padding:16px 20px;margin-bottom:16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
      <div style="flex:1">
        <div style="font-size:0.75rem;color:var(--gris);text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Cliente</div>
        <select id="pres-cliente-sel" onchange="cambiarClientePresupuesto(${p.id})"
          style="border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;font-size:0.9rem;background:var(--crema);min-width:200px">
          <option value="">Sin cliente</option>
          ${clientes.map(cl => `<option value="${cl.id}" ${cl.id===p.cliente_id?'selected':''}>${cl.nombre}</option>`).join('')}
        </select>
      </div>
      ${p.cliente_nombre ? `
        <div style="font-size:0.85rem;color:var(--gris);line-height:1.6">
          ${p.cliente_telefono ? `📞 ${p.cliente_telefono}<br>` : ''}
          ${p.cliente_email ? `✉️ ${p.cliente_email}` : ''}
        </div>` : ''}
    </div>

    <!-- Items -->
    <div style="background:var(--blanco);border-radius:14px;box-shadow:var(--sombra);padding:20px;margin-bottom:16px">
      <div style="font-family:'Playfair Display',serif;font-size:1.1rem;color:var(--marron);margin-bottom:14px">Productos / Servicios</div>
      <div id="pres-items">
        ${renderPresupuestoItems(p.items)}
      </div>

      <!-- Agregar item -->
      <div style="border-top:1px solid #f0e4d8;margin-top:14px;padding-top:14px">
        <div style="font-size:0.75rem;color:var(--gris);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Agregar producto</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
          <div style="flex:2;min-width:160px">
            <label style="font-size:0.72rem;color:var(--gris);display:block;margin-bottom:3px">Descripción</label>
            <input type="text" id="add-item-desc" placeholder="Ej: Torta de chocolate" list="recetas-list"
              style="width:100%;border:1.5px solid #e8d8cc;border-radius:8px;padding:7px 10px;font-family:'DM Sans',sans-serif;font-size:0.88rem;background:var(--crema)"/>
            <datalist id="recetas-list">
              ${recetas.map(r => `<option value="${r.nombre}" data-id="${r.id}" data-precio="${r.precio_final}">`).join('')}
            </datalist>
          </div>
          <div>
            <label style="font-size:0.72rem;color:var(--gris);display:block;margin-bottom:3px">Cantidad</label>
            <input type="number" id="add-item-cant" value="1" min="1" style="width:70px;border:1.5px solid #e8d8cc;border-radius:8px;padding:7px 10px;font-family:'DM Sans',sans-serif;font-size:0.88rem;background:var(--crema)"/>
          </div>
          <div>
            <label style="font-size:0.72rem;color:var(--gris);display:block;margin-bottom:3px">Precio unit. ($)</label>
            <input type="number" id="add-item-precio" placeholder="0" style="width:120px;border:1.5px solid #e8d8cc;border-radius:8px;padding:7px 10px;font-family:'DM Sans',sans-serif;font-size:0.88rem;background:var(--crema)"/>
          </div>
          <button class="btn-primary" onclick="agregarItem(${p.id})" style="padding:8px 18px">+ Agregar</button>
        </div>
      </div>
    </div>

    <!-- Total + notas -->
    <div style="display:grid;grid-template-columns:1fr auto;gap:16px;align-items:start;flex-wrap:wrap">
      <div style="background:var(--blanco);border-radius:14px;box-shadow:var(--sombra);padding:16px 20px">
        <div style="font-size:0.75rem;color:var(--gris);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">📝 Notas para el cliente</div>
        <textarea id="pres-notas" placeholder="Incluye entrega a domicilio, decoración personalizada..."
          style="width:100%;border:1.5px solid #e8d8cc;border-radius:10px;padding:10px 14px;font-family:'DM Sans',sans-serif;font-size:0.88rem;background:var(--crema);resize:vertical;min-height:80px"
          onchange="guardarNotasPresupuesto(${p.id})">${p.notas || ''}</textarea>
      </div>
      <div style="background:var(--marron);color:var(--crema);border-radius:14px;padding:20px 28px;text-align:center;min-width:160px">
        <div style="font-size:0.75rem;opacity:0.7;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Total</div>
        <div id="pres-total" style="font-family:'Playfair Display',serif;font-size:2rem;color:var(--amarillo)">${fmt(p.total)}</div>
      </div>
    </div>
  `;

  // Auto-completar precio al seleccionar receta
  document.getElementById('add-item-desc').addEventListener('input', function() {
    const match = recetas.find(r => r.nombre === this.value);
    if (match) document.getElementById('add-item-precio').value = Math.round(match.precio_final);
  });
}

function renderPresupuestoItems(items) {
  if (!items.length) return '<div style="color:var(--gris);font-style:italic;padding:8px">Sin productos aún</div>';
  return items.map(item => `
    <div class="ing-detalle-row" id="pres-item-${item.id}">
      <div class="ing-row-vista">
        <span class="nombre">${item.descripcion}</span>
        <span class="cant" style="min-width:50px">x${item.cantidad}</span>
        <span class="costo">${fmt(item.precio_unit)} c/u</span>
        <span class="costo" style="font-size:1rem">${fmt(item.precio_total)}</span>
        <button class="btn-editar-ing" onclick="toggleEditItem(${item.id})" title="Editar">✏️</button>
        <button class="btn-del" onclick="eliminarItem(${presupuestoDetalle.id}, ${item.id})">✕</button>
      </div>
      <div class="ing-row-edit">
        <div>
          <label>Descripción</label>
          <input type="text" id="edit-item-desc-${item.id}" value="${item.descripcion}" style="width:200px;border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;"/>
        </div>
        <div>
          <label>Cantidad</label>
          <input type="number" id="edit-item-cant-${item.id}" value="${item.cantidad}" min="1" style="width:70px;border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;"/>
        </div>
        <div>
          <label>Precio unit. ($)</label>
          <input type="number" id="edit-item-precio-${item.id}" value="${item.precio_unit}" style="width:110px;border:1.5px solid #e8d8cc;border-radius:8px;padding:6px 10px;font-family:'DM Sans',sans-serif;"/>
        </div>
        <button class="btn-save-ing" onclick="guardarItem(${presupuestoDetalle.id}, ${item.id}, ${item.receta_id||'null'})">✓ Guardar</button>
        <button class="btn-cancel-ing" onclick="toggleEditItem(${item.id})">Cancelar</button>
      </div>
    </div>
  `).join('');
}

function toggleEditItem(itemId) {
  document.getElementById(`pres-item-${itemId}`)?.classList.toggle('editando');
}

async function agregarItem(presupuestoId) {
  const desc = document.getElementById('add-item-desc').value.trim();
  const cant = parseInt(document.getElementById('add-item-cant').value) || 1;
  const precio = parseFloat(document.getElementById('add-item-precio').value);
  if (!desc) { toast('Completá la descripción', '#e8a598'); return; }
  if (isNaN(precio) || precio <= 0) { toast('Ingresá un precio válido', '#e8a598'); return; }
  const receta = recetas.find(r => r.nombre === desc);
  const data = await post(`/presupuestos/${presupuestoId}/items`, {
    descripcion: desc, cantidad: cant, precio_unit: precio,
    receta_id: receta ? receta.id : null
  });
  presupuestoDetalle = data;
  presupuestos = await get('/presupuestos');
  renderPresupuestoDetalle(document.getElementById('app'));
  toast('✓ Producto agregado');
}

async function guardarItem(presupuestoId, itemId, recetaId) {
  const desc = document.getElementById(`edit-item-desc-${itemId}`).value.trim();
  const cant = parseInt(document.getElementById(`edit-item-cant-${itemId}`).value) || 1;
  const precio = parseFloat(document.getElementById(`edit-item-precio-${itemId}`).value);
  if (!desc || isNaN(precio) || precio <= 0) { toast('Datos inválidos', '#e8a598'); return; }
  const data = await put(`/presupuestos/${presupuestoId}/items/${itemId}`, {
    descripcion: desc, cantidad: cant, precio_unit: precio, receta_id: recetaId
  });
  presupuestoDetalle = data;
  presupuestos = await get('/presupuestos');
  renderPresupuestoDetalle(document.getElementById('app'));
  toast('✓ Producto actualizado');
}

async function eliminarItem(presupuestoId, itemId) {
  const data = await del(`/presupuestos/${presupuestoId}/items/${itemId}`);
  presupuestoDetalle = data;
  presupuestos = await get('/presupuestos');
  document.getElementById('pres-items').innerHTML = renderPresupuestoItems(presupuestoDetalle.items);
  document.getElementById('pres-total').textContent = fmt(presupuestoDetalle.total);
  toast('Producto quitado', '#c97b6e');
}

async function guardarTituloPresupuesto(id) {
  const titulo = document.getElementById('pres-titulo-input').value.trim();
  if (!titulo) return;
  await put(`/presupuestos/${id}`, { titulo });
  presupuestoDetalle.titulo = titulo;
  presupuestos = await get('/presupuestos');
  document.getElementById('btn-save-pres-titulo').style.display = 'none';
  toast('✓ Título guardado');
}

async function cambiarEstadoPresupuesto(id) {
  const estado = document.getElementById('pres-estado-sel').value;
  await put(`/presupuestos/${id}`, { estado });
  presupuestoDetalle.estado = estado;
  presupuestos = await get('/presupuestos');
  const sel = document.getElementById('pres-estado-sel');
  sel.style.background = ESTADO_COLOR[estado];
  sel.style.color = ESTADO_TEXT[estado];
  toast('✓ Estado actualizado');
}

async function cambiarClientePresupuesto(id) {
  const cliente_id = document.getElementById('pres-cliente-sel').value;
  const data = await put(`/presupuestos/${id}`, { cliente_id: cliente_id ? parseInt(cliente_id) : null });
  presupuestoDetalle = data;
  presupuestos = await get('/presupuestos');
  toast('✓ Cliente actualizado');
}

async function guardarNotasPresupuesto(id) {
  const notas = document.getElementById('pres-notas').value;
  await put(`/presupuestos/${id}`, { notas });
  presupuestoDetalle.notas = notas;
  toast('✓ Notas guardadas');
}

async function eliminarPresupuesto(id) {
  if (!confirm('¿Eliminar este presupuesto?')) return;
  await del(`/presupuestos/${id}`);
  presupuestos = await get('/presupuestos');
  volverPresupuestos();
  toast('Presupuesto eliminado', '#c97b6e');
}

function volverPresupuestos() {
  presupuestoDetalle = null;
  tabActual = 'presupuestos';
  render();
}

function imprimirPresupuesto() {
  const p = presupuestoDetalle;
  const itemsHTML = p.items.map(i =>
    `<tr><td>${i.descripcion}</td><td style="text-align:center">${i.cantidad}</td><td style="text-align:right">${fmt(i.precio_unit)}</td><td style="text-align:right"><strong>${fmt(i.precio_total)}</strong></td></tr>`
  ).join('');
  const win = window.open('', '_blank');
  win.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8">
  <title>Presupuesto - ${p.titulo}</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 700px; margin: 40px auto; color: #3a2a22; }
    h1 { color: #5c3d2e; border-bottom: 2px solid #e8a598; padding-bottom: 8px; }
    .meta { color: #9e8a80; font-size: 0.9rem; margin-bottom: 24px; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th { background: #5c3d2e; color: #fdf6ee; padding: 10px 12px; text-align: left; }
    td { padding: 10px 12px; border-bottom: 1px solid #f0e4d8; }
    tr:hover td { background: #fdf6ee; }
    .total-row { font-size: 1.2rem; font-weight: bold; background: #fdf6ee; }
    .notas { background: #fff8e6; border-left: 4px solid #f4c96e; padding: 12px 16px; border-radius: 4px; margin-top: 20px; font-size: 0.9rem; }
    .footer { text-align: center; color: #9e8a80; font-size: 0.8rem; margin-top: 40px; }
  </style></head><body>
  <h1>🧁 Roxi Pastelería</h1>
  <h2 style="margin-bottom:4px">${p.titulo}</h2>
  <div class="meta">
    ${p.cliente_nombre ? `👥 <strong>${p.cliente_nombre}</strong>${p.cliente_telefono ? ' · 📞 '+p.cliente_telefono : ''}${p.cliente_email ? ' · ✉️ '+p.cliente_email : ''}<br>` : ''}
    📅 ${new Date(p.created_at).toLocaleDateString('es-AR', {year:'numeric',month:'long',day:'numeric'})}
    &nbsp;·&nbsp; Estado: <strong>${ESTADOS[p.estado]||p.estado}</strong>
  </div>
  <table>
    <thead><tr><th>Producto / Servicio</th><th style="text-align:center">Cant.</th><th style="text-align:right">Precio unit.</th><th style="text-align:right">Total</th></tr></thead>
    <tbody>${itemsHTML}</tbody>
    <tfoot><tr class="total-row"><td colspan="3" style="text-align:right;padding-right:12px">TOTAL</td><td style="text-align:right">${fmt(p.total)}</td></tr></tfoot>
  </table>
  ${p.notas ? `<div class="notas"><strong>📝 Notas:</strong><br>${p.notas}</div>` : ''}
  <div class="footer">Roxi Pastelería · Sistema de Costeo</div>
  </body></html>`);
  win.document.close();
  win.print();
}
</script>
</body>
</html>
