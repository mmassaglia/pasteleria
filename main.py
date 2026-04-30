from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import psycopg2
import psycopg2.extras
import os

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
def listar_ingredientes():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM ingredientes ORDER BY nombre")
    rows = c.fetchall()
    c.close()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/ingredientes", tags=["Ingredientes"], summary="Crear nuevo ingrediente")
def crear_ingrediente(data: IngredienteCreate):
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
def actualizar_ingrediente(ing_id: int, data: IngredienteUpdate):
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
def eliminar_ingrediente(ing_id: int):
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
def listar_recetas():
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
def obtener_receta(receta_id: int):
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
def crear_receta(data: RecetaCreate):
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
def actualizar_receta(receta_id: int, data: RecetaUpdate):
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
def eliminar_receta(receta_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM receta_ingredientes WHERE receta_id=%s", (receta_id,))
    c.execute("DELETE FROM recetas WHERE id=%s", (receta_id,))
    conn.commit()
    c.close()
    conn.close()
    return {"mensaje": "Receta eliminada"}

@app.post("/recetas/{receta_id}/ingredientes", tags=["Recetas"], summary="Agregar ingrediente a receta")
def agregar_ingrediente_receta(receta_id: int, item: RecetaIngredienteItem):
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
def actualizar_ingrediente_receta(receta_id: int, ri_id: int, item: RecetaIngredienteItem):
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
def quitar_ingrediente_receta(receta_id: int, ri_id: int):
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
def resumen():
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
def descargar_backup():
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
# FRONTEND
# ─────────────────────────────────────────

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    with open("frontend/index.html", encoding="utf-8") as f:
        return f.read()
