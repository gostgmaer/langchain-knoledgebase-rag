import uvicorn

from packages.container import container


def main():
    settings = container.settings()
    logger = container.logger()

    logger.info(settings.app.name)
    logger.info(settings.app.version)

    uvicorn.run(
        "packages.api.app:app",
        host=settings.api.host,
        port=settings.api.port,
    )


if __name__ == "__main__":
    main()
