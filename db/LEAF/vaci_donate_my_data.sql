-- phpMyAdmin SQL Dump
-- version 4.3.11.1
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Mar 31, 2015 at 02:15 PM
-- Server version: 10.0.16-MariaDB-log
-- PHP Version: 5.6.5

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `vaci_donate_my_data`
--

-- --------------------------------------------------------

--
-- Table structure for table `data`
--

CREATE TABLE IF NOT EXISTS `data` (
  `recordID` smallint(5) unsigned NOT NULL,
  `indicatorID` smallint(5) NOT NULL,
  `series` tinyint(3) unsigned NOT NULL DEFAULT '1',
  `data` text NOT NULL,
  `timestamp` int(10) unsigned NOT NULL DEFAULT '0',
  `userID` varchar(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `records`
--

CREATE TABLE IF NOT EXISTS `records` (
  `recordID` smallint(5) unsigned NOT NULL,
  `date` int(10) unsigned NOT NULL,
  `serviceID` smallint(5) unsigned NOT NULL DEFAULT '0',
  `userID` varchar(50) NOT NULL,
  `title` text,
  `priority` tinyint(4) NOT NULL DEFAULT '0',
  `lastStatus` varchar(200) DEFAULT NULL,
  `submitted` int(10) NOT NULL DEFAULT '0',
  `deleted` int(10) NOT NULL DEFAULT '0',
  `isWritableUser` tinyint(3) unsigned NOT NULL DEFAULT '1',
  `isWritableGroup` tinyint(3) unsigned NOT NULL DEFAULT '1'
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `data`
--
ALTER TABLE `data`
  ADD UNIQUE KEY `unique` (`recordID`,`indicatorID`,`series`), ADD KEY `indicator_series` (`indicatorID`,`series`);

--
-- Indexes for table `records`
--
ALTER TABLE `records`
  ADD PRIMARY KEY (`recordID`), ADD KEY `date` (`date`), ADD KEY `deleted` (`deleted`), ADD KEY `serviceID` (`serviceID`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `records`
--
ALTER TABLE `records`
  MODIFY `recordID` smallint(5) unsigned NOT NULL AUTO_INCREMENT,AUTO_INCREMENT=22;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
