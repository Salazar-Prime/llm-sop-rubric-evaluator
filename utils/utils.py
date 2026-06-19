import os
import logging
import re
import time
from logging.handlers import RotatingFileHandler


def cleanTextForExcel(text):
    if not isinstance(text, str):
        return text
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    text = text.replace(' ', ' ').replace(' ', ' ')
    text = ' '.join(text.split())
    return text


def setupLogger(outputDir, logFileName='processing.log', continueWithLastFile=False):
    os.makedirs(outputDir, exist_ok=True)

    logger = logging.getLogger(__name__)

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logPath = os.path.join(outputDir, logFileName)

    if os.path.exists(logPath) and not continueWithLastFile:
        try:
            timestamp = os.path.getmtime(logPath)
            timeStr = time.strftime('%Y%m%d_%H%M%S', time.localtime(timestamp))
            os.rename(logPath, f"{logPath}.{timeStr}")
        except Exception as e:
            print(f"Warning: Could not rotate existing log file: {e}")

    fileMode = 'a' if continueWithLastFile else 'w'

    fileHandler = RotatingFileHandler(
        logPath,
        maxBytes=1024 * 1024,
        backupCount=5,
        mode=fileMode,
    )
    fileHandler.setFormatter(formatter)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(formatter)

    logger.addHandler(fileHandler)
    logger.addHandler(consoleHandler)

    if continueWithLastFile and os.path.exists(logPath):
        logger.info("-" * 80)
        logger.info("Continuing logging in existing file")
        logger.info(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        logger.info("-" * 80)

    return logger
