#!/usr/bin/env python
"""
Database initialization script
Creates the database and initial superuser
"""

import asyncio
import sys
from getpass import getpass

from app.db.database import db_manager
from app.schemas.user import UserCreate
from app.services.user import create_user


async def init_database():
    print("🚀 Initializing database...")
    
    # Initialize database connection
    await db_manager.initialize()
    
    # Create all tables
    print("📋 Creating database tables...")
    await db_manager.create_tables()
    print("✅ Tables created successfully!")
    
    # Check if demo mode
    from app.core.config import settings
    if settings.IS_DEMO_MODE:
        print("\n🎮 Demo Mode Detected!")
        print("Creating demo user account...")

        async with db_manager.async_session_maker() as session:
            # Check if demo user already exists
            from app.services.user import get_user_by_email
            existing_user = await get_user_by_email(session, "demo@example.com")
            
            if not existing_user:
                demo_user = UserCreate(
                    email="demo@example.com",
                    username="demo_user",
                    password="demo123",
                    full_name="Demo User",
                    is_active=True,
                    is_superuser=False,
                    is_verified=True
                )
                
                try:
                    user = await create_user(session, demo_user)
                    print("✅ Demo user created successfully!")
                    print("   Email: demo@example.com")
                    print("   Password: demo123")
                except Exception as e:
                    print(f"❌ Error creating demo user: {e}")
            else:
                print("ℹ️ Demo user already exists.")
    
    # Ask if user wants to create a superuser
    create_super = input("\nDo you want to create a superuser account? (y/n): ").lower()
    
    if create_super == 'y':
        print("\n👤 Creating superuser account...")
        
        email = input("Email: ")
        username = input("Username: ")
        password = getpass("Password: ")
        confirm_password = getpass("Confirm password: ")
        
        if password != confirm_password:
            print("❌ Passwords do not match!")
            return
        
        # Create superuser
        async with db_manager.async_session_maker() as session:
            user_data = UserCreate(
                email=email,
                username=username,
                password=password,
                is_active=True,
                is_superuser=True,
                is_verified=True
            )
            
            try:
                user = await create_user(session, user_data)
                print(f"✅ Superuser '{username}' created successfully!")
            except Exception as e:
                print(f"❌ Error creating superuser: {e}")
    
    # Close database connection
    await db_manager.close()
    print("\n🎉 Database initialization complete!")


if __name__ == "__main__":
    try:
        asyncio.run(init_database())
    except KeyboardInterrupt:
        print("\n⚠️ Database initialization cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)