from app.domain.enums import CategoryType

CATEGORY_KEYWORDS = {
    # 🥩 Alimentación
    "mercado": "Mercado", "despensa": "Mercado",
    "almuerzo": "Comida Fuera", "menu": "Comida Fuera", "restaurant": "Comida Fuera",
    "galletas": "Antojos", "snack": "Antojos", "cafe": "Antojos",
    # 🚌 Transporte
    "pasaje": "Transporte Diario", "bus": "Transporte Diario", "corredor": "Transporte Diario",
    "uber": "Taxis / Apps", "yango": "Taxis / Apps", "indriver": "Taxis / Apps",
    # 🏋️ Powerlifting & Salud
    "creatina": "Suplementación", "proteina": "Suplementación",
    "gym": "Gimnasio & Equipamiento", "magnesio": "Gimnasio & Equipamiento",
    "fisio": "Recuperación", "masaje": "Recuperación",
    # 💻 Tecnología & Laboratorios
    "vps": "Servidores e Infraestructura", "digitalocean": "Servidores e Infraestructura",
    "aws": "Servidores e Infraestructura",
    "openai": "Suscripciones IA & APIs", "chatgpt": "Suscripciones IA & APIs",
    "claude": "Suscripciones IA & APIs", "gemini": "Suscripciones IA & APIs",
    "tokens": "Suscripciones IA & APIs",
    # 🎓 Universidad & Desarrollo
    "certificacion": "Certificaciones", "examen": "Certificaciones",
    "tramite": "Trámites & Universidad", "constancia": "Trámites & Universidad",
    "tesis": "Proyectos Grupales", "grupo": "Proyectos Grupales", "juntada": "Proyectos Grupales",
    # 📱 Servicios, Ocio y Otros
    "celular": "Servicios Básicos", "internet": "Servicios Básicos", "plan": "Servicios Básicos",
    "netflix": "Entretenimiento", "spotify": "Entretenimiento",
    "cine": "Vida Social", "bar": "Vida Social", "fiesta": "Vida Social",
    "corte": "Gastos Personales", "barberia": "Gastos Personales", "ropa": "Gastos Personales",
}

_SEED_PARENTS = [
    {"name": "Alimentación", "type": CategoryType.EXPENSE, "icon": "🥩", "color": "#FF6B6B"},
    {"name": "Transporte", "type": CategoryType.EXPENSE, "icon": "🚌", "color": "#4ECDC4"},
    {"name": "Powerlifting & Salud", "type": CategoryType.EXPENSE, "icon": "🏋️", "color": "#95E1D3"},
    {"name": "Tecnología & Laboratorios", "type": CategoryType.EXPENSE, "icon": "💻", "color": "#6C5CE7"},
    {"name": "Universidad & Desarrollo", "type": CategoryType.EXPENSE, "icon": "🎓", "color": "#FDCB6E"},
    {"name": "Servicios, Ocio y Otros", "type": CategoryType.EXPENSE, "icon": "📱", "color": "#E17055"},
    {"name": "Ingresos", "type": CategoryType.INCOME, "icon": "💰", "color": "#00B894"},
    {"name": "Condominio", "type": CategoryType.CONDO, "icon": "🏢", "color": "#636E72"},
    {"name": "Préstamos", "type": CategoryType.EXPENSE, "icon": "💳", "color": "#2D3436"},
]

# (name, icon, color[, type_override])
_SEED_CHILDREN: dict[str, list[tuple[str, str, str, str | None]]] = {
    "Alimentación": [("Mercado", "🛒", "#FF8A8A", None), ("Comida Fuera", "🍔", "#FF5252", None), ("Antojos", "🍪", "#FFB3B3", None)],
    "Transporte": [("Transporte Diario", "🚍", "#7DD5CF", None), ("Taxis / Apps", "🚖", "#2EBDB4", None)],
    "Powerlifting & Salud": [("Suplementación", "💊", "#B8ECD9", None), ("Gimnasio & Equipamiento", "🏋️", "#6ED4C4", None), ("Recuperación", "🩹", "#D4F5EC", None)],
    "Tecnología & Laboratorios": [("Servidores e Infraestructura", "🖥️", "#8B7CF7", None), ("Suscripciones IA & APIs", "🤖", "#4A3DB5", None)],
    "Universidad & Desarrollo": [("Certificaciones", "📜", "#FDE3A7", None), ("Trámites & Universidad", "📋", "#FECA57", None), ("Proyectos Grupales", "👥", "#FFEAA7", None)],
    "Servicios, Ocio y Otros": [
        ("Servicios Básicos", "📡", "#E59866", None), ("Entretenimiento", "🎬", "#E17055", None), ("Vida Social", "🍻", "#D35400", None), ("Gastos Personales", "✂️", "#EDBB99", None),
    ],
    "Préstamos": [
        ("Prestado", "💸", "#636E72", None), ("Cobro Préstamo", "💰", "#B2BEC3", CategoryType.INCOME),
    ],
}
