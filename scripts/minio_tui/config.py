from dynaconf import Dynaconf
import os

# Get the current working directory from where the script is run
CWD = os.getcwd()

settings = Dynaconf(
    envvar_prefix="MINIO_TUI",
    # Explicitly tell dynaconf to look for these files using absolute paths
    settings_files=[
        os.path.join(CWD, 'config.toml'),
        os.path.join(CWD, '.secrets.toml')
    ],
    load_dotenv=True,
    # Also use an absolute path for the .env file
    dotenv_path=os.path.join(CWD, '.env'),
)
