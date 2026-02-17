import asyncio
import sys
from pathlib import Path


def _ensure_backend_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    backend_dir = root / "backend"
    sys.path.insert(0, str(backend_dir))


async def main() -> None:
    _ensure_backend_on_path()

    from functions.users import create_user
    from functions.flags import create_flag

    admin = await create_user(
        email="admin@test.com",
        first_name="TestAdmin",
        password="admin123",
        role="admin",
    )
    if admin:
        print("Created admin: admin@test.com / admin123")
    else:
        print("Admin already exists or conflict")

    experimenter = await create_user(
        email="experimenter@test.com",
        first_name="TestExperimenter",
        password="exp123",
        role="experimenter",
    )
    if experimenter:
        print("Created experimenter: experimenter@test.com / exp123")
    else:
        print("Experimenter already exists or conflict")

    flag = await create_flag(
        key="test_feature_flag",
        value_type="string",
        default_value="control",
        description="Flag for API tests",
    )
    if flag:
        print(f"Created flag: test_feature_flag (id={flag.get('id')})")
    else:
        print("Flag test_feature_flag already exists")

    print("Seed done.")


if __name__ == "__main__":
    asyncio.run(main())

