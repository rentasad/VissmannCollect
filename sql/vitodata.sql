-- --------------------------------------------------------
-- Host:                         192.168.171.11
-- Server-Version:               8.4.4 - MySQL Community Server - GPL
-- Server-Betriebssystem:        Linux
-- HeidiSQL Version:             12.10.0.7000
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Exportiere Datenbank-Struktur für vitocal
CREATE DATABASE IF NOT EXISTS `vitocal` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `vitocal`;

-- Exportiere Struktur von Tabelle vitocal.vitodata
CREATE TABLE IF NOT EXISTS `vitodata` (
  `id` int NOT NULL AUTO_INCREMENT,
  `timestamp` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `installation_id` int DEFAULT NULL,
  `gateway_serial` varchar(50) DEFAULT NULL,
  `device_id` varchar(10) DEFAULT NULL,
  `aussentemperatur` float DEFAULT NULL,
  `vorlauftemperatur_hk` float DEFAULT NULL,
  `vorlauftemperatur_fb` float DEFAULT NULL,
  `ruecklauftemperatur` float DEFAULT NULL,
  `sekundaerkreis_vorlauf` float DEFAULT NULL,
  `warmwasser_oben` float DEFAULT NULL,
  `warmwasser_soll` float DEFAULT NULL,
  `kompressor_anzahl_starts` int DEFAULT NULL,
  `kompressor_laufzeit_h` float DEFAULT NULL,
  `kompressor_status` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17924 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Daten-Export vom Benutzer nicht ausgewählt

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
