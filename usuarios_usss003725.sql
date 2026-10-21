-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Tiempo de generación: 22-10-2026 a las 01:30:49
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `db_academica`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `usuarios_usss003725`
--

CREATE TABLE `usuarios_usss003725` (
  `idUsuario` int(10) NOT NULL,
  `usuario` char(35) NOT NULL,
  `clave` char(35) NOT NULL,
  `nombre` char(85) NOT NULL,
  `dirección` char(100) DEFAULT NULL,
  `teléfono` char(9) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `usuarios_usss003725`
--

INSERT INTO `usuarios_usss003725` (`idUsuario`, `usuario`, `clave`, `nombre`, `dirección`, `teléfono`) VALUES
(1, 'admin', '1234', 'Administrador UGB', 'Usulután', '7000-0000'),
(2, 'Kim', '12345', 'Kimberly Michelle Castro Zelaya', 'Usulutan', '1234-7878'),
(5, 'UGBUSU', 'UGBUSO2026', 'Luis', 'Usulutan', '1234-7870'),
(6, 'Saul', '1234', 'Saul Jimenez', 'Ozatlan', '2323-7874');

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `usuarios_usss003725`
--
ALTER TABLE `usuarios_usss003725`
  ADD PRIMARY KEY (`idUsuario`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `usuarios_usss003725`
--
ALTER TABLE `usuarios_usss003725`
  MODIFY `idUsuario` int(10) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
