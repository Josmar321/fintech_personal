"""Seed default categories for the admin user."""
import asyncio
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database.base import Base
from app.database.models.category import Category
from app.database.models.user import User
from app.domain.enums import CategoryType

ENGINE_URL = "mssql+aioodbc://sa:SaiD-2024$@sqlserver:1433/fintech_personal?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"


async def seed():
    engine = create_async_engine(ENGINE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name='categories')
            BEGIN
                CREATE TABLE categories (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    user_id INT NOT NULL FOREIGN KEY REFERENCES users(id),
                    name VARCHAR(100) NOT NULL,
                    type VARCHAR(20) NOT NULL,
                    icon VARCHAR(50),
                    color VARCHAR(7),
                    parent_id INT FOREIGN KEY REFERENCES categories(id),
                    is_system BIT NOT NULL DEFAULT 0,
                    is_active BIT NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT GETDATE(),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            END
        """))

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(select(User).order_by(User.id).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("No user found. Create one first.")
            return

        uid = user.id

        result = await session.execute(select(Category).where(Category.user_id == uid).limit(1))
        if result.scalar_one_or_none():
            print("Categories already exist for this user.")
            return

        parents = [
            {"name": "Alimentación", "type": CategoryType.EXPENSE, "icon": "🥩"},
            {"name": "Transporte", "type": CategoryType.EXPENSE, "icon": "🚌"},
            {"name": "Powerlifting & Salud", "type": CategoryType.EXPENSE, "icon": "🏋️"},
            {"name": "Tecnología & Laboratorios", "type": CategoryType.EXPENSE, "icon": "💻"},
            {"name": "Universidad & Desarrollo", "type": CategoryType.EXPENSE, "icon": "🎓"},
            {"name": "Servicios, Ocio y Otros", "type": CategoryType.EXPENSE, "icon": "📱"},
            {"name": "Ingresos", "type": CategoryType.INCOME, "icon": "💰"},
        ]

        children_map = {
            "Alimentación": [
                ("Mercado", "🛒"),
                ("Comida Fuera", "🍔"),
                ("Antojos", "🍪"),
            ],
            "Transporte": [
                ("Transporte Diario", "🚍"),
                ("Taxis / Apps", "🚖"),
            ],
            "Powerlifting & Salud": [
                ("Suplementación", "💊"),
                ("Gimnasio & Equipamiento", "🏋️"),
                ("Recuperación", "🩹"),
            ],
            "Tecnología & Laboratorios": [
                ("Servidores e Infraestructura", "🖥️"),
                ("Suscripciones IA & APIs", "🤖"),
            ],
            "Universidad & Desarrollo": [
                ("Certificaciones", "📜"),
                ("Trámites & Universidad", "📋"),
                ("Proyectos Grupales", "👥"),
            ],
            "Servicios, Ocio y Otros": [
                ("Servicios Básicos", "📡"),
                ("Entretenimiento", "🎬"),
                ("Vida Social", "🍻"),
                ("Gastos Personales", "✂️"),
            ],
        }

        created_parents = {}
        for p in parents:
            cat = Category(
                user_id=uid,
                name=p["name"],
                type=p["type"],
                icon=p["icon"],
                is_system=True,
                is_active=True,
            )
            session.add(cat)
            await session.flush()
            created_parents[p["name"]] = cat.id

        for parent_name, children in children_map.items():
            parent_id = created_parents.get(parent_name)
            if not parent_id:
                continue
            for child_name, icon in children:
                cat = Category(
                    user_id=uid,
                    name=child_name,
                    type=CategoryType.EXPENSE,
                    icon=icon,
                    parent_id=parent_id,
                    is_system=True,
                    is_active=True,
                )
                session.add(cat)

        await session.commit()
        print(f"Seeded {len(parents)} parent categories and children for user {uid} (email={user.email})")


if __name__ == "__main__":
    asyncio.run(seed())
