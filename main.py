from packages.container import container
def main():
   

    settings = container.settings()
    logger = container.logger()

    logger.info(settings.app.name)
    logger.info(settings.app.version)


if __name__ == "__main__":
    main()
