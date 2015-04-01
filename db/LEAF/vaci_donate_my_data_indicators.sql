--
-- Database: `vaci_donate_my_data`
--

-- --------------------------------------------------------

--
-- Table structure for table `indicators`
--

CREATE TABLE IF NOT EXISTS `indicators` (
  `indicatorID` smallint(5) NOT NULL,
  `name` text NOT NULL,
  `format` text NOT NULL,
  `description` varchar(50) DEFAULT NULL,
  `default` varchar(20) DEFAULT NULL,
  `parentID` smallint(5) unsigned DEFAULT NULL,
  `categoryID` varchar(20) DEFAULT NULL,
  `html` text,
  `htmlPrint` text,
  `jsSort` varchar(255) DEFAULT NULL,
  `required` tinyint(4) NOT NULL DEFAULT '0',
  `sort` tinyint(4) NOT NULL DEFAULT '1',
  `timeAdded` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `disabled` tinyint(4) NOT NULL DEFAULT '0'
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8;

--
-- Dumping data for table `indicators`
--

INSERT INTO `indicators` (`indicatorID`, `name`, `format`, `description`, `default`, `parentID`, `categoryID`, `html`, `htmlPrint`, `jsSort`, `required`, `sort`, `timeAdded`, `disabled`) VALUES
(1, '<h1>Purpose</h1><p>VA asks you to donate the information in your VA electronic health record to improve VA health care software.</p><p>VA currently uses made-up data to test new software programs. This data cannot duplicate the real-life experiences needed for accurate testing.  That is why VA asks you to contribute your personal health data to the Donate My Data program. If you agree, the Donate My Data program will use your health-related data, without your name or other ways to identify you, described below, to develop and test health care software for the Veterans Health Administration.</p>', 'text', 'Purpose', 'I understand', NULL, 'donate', '<script>$(function(){$(''#1'').css(''display'', ''none'');});</script>', '<script>$(function(){$(''#xhrIndicator_1_1'').css(''display'', ''none'');});</script>', NULL, 1, 1, '2014-09-08 13:10:11', 0),
(2, '<h1>YOUR ELECTRONIC HEALTH-RELATED DATA</h1><p>For the Donate My Data program, VA requests access to all of your electronic health data beginning the day you first entered the VA health care system. Health data includes your vital signs, diagnoses, health record notes, medications, treatment history, laboratory tests and all other information found in your electronic health record.  VA will use the year you were born and your age, but <u>not</u> your name, full Social Security number, street address (e.g., 123 Main Street), phone numbers, or your birth month or day.</p>', 'text', 'Your Data', 'I understand', NULL, 'donate', '<script>\n$(function(){\n$(''#2'').css(''display'', ''none'');\n});\n</script>', '<script>$(function(){$(''#xhrIndicator_2_1'').css(''display'', ''none'');});</script>', NULL, 1, 1, '2014-09-08 13:15:23', 0),
(3, '<h1>BENEFITS</h1><p>You will not receive any direct benefit by contributing your data to the Donate My Data program. Your contribution will not affect your medical care, benefit eligibility or VA employment.  Your contribution will help VA develop new health care software to improve the quality of care delivered to Veterans.</p>', 'text', 'Benefits', 'I understand', NULL, 'donate', '<script>\n$(function(){\n$(''#3'').css(''display'', ''none'');\n});\n</script>', '<script>$(function(){$(''#xhrIndicator_3_1'').css(''display'', ''none'');});</script>', NULL, 1, 1, '2014-09-08 13:17:42', 0),
(4, '<h1>PROTECTING YOUR PRIVACY</h1><p>Law requires VA to maintain and safeguard the privacy of Veterans’ information. Your privacy and the confidentiality of your data are very important to us.  Though it is impossible to eliminate all privacy risks, VA will make every possible effort to safeguard the health information you contribute to the Donate My Data program.</p><p>The health data that you contribute will be stored and used separately from your VA electronic health record.  We will not place any information into your VA electronic health record.  All data are protected using current security and data protection mechanisms.  We will take appropriate actions to ensure that only authorized personnel have access to your data and use only the data required to achieve the goals of the Donate My Data program.</p>', 'text', 'Privacy', 'I understand', NULL, 'donate', '<script>\n$(function(){\n$(''#4'').css(''display'', ''none'');\n});\n</script>', '<script>$(function(){$(''#xhrIndicator_4_1'').css(''display'', ''none'');});</script>', NULL, 1, 1, '2014-09-08 17:40:55', 0),
(5, '<h1>YOUR CONTRIBUTION</h1><p>If you choose to contribute your health data, VA will use your health-related data for five years. VA will stop using your data should you pass away during that period.  We will not use your data at the end of the five-year term without a new agreement from you. In addition, you may tell us to stop using your data at any time.</p><p>There is no financial cost to you for contributing to this program.</p><p>You do not need to do anything after you complete and submit this form. We will contact you:\r\n<ul><li>If there are significant changes to the program,</li>\r\n<li>If we become aware of a risk to your privacy, and/or</li>\r\n<li>To offer re-enrollment at the end of the five-year period.</li>\r\n</ul></p>', 'text', 'Your Contribution', 'I understand', NULL, 'donate', '<script>\n$(function(){\n$(''#5'').css(''display'', ''none'');\n});\n</script>', '<script>$(function(){$(''#xhrIndicator_5_1'').css(''display'', ''none'');});</script>', NULL, 1, 1, '2014-09-08 17:41:36', 0),
(6, '<h1>HOW TO LEAVE THE PROGRAM</h1><p>You may tell us to stop using your health data for the Donate My Data program at any time.  Email <a href="mailto: donatemydata@va.gov">donatemydata@va.gov</a> to withdraw your contribution.  Someone from VA will contact you within two business days to complete the process of removing your data from the Donate My Data program.  </p><p>If you decide to leave the program, we will keep your original agreement form and your request to withdraw your contribution.  We will immediately remove your health record from our Donate My Data master database; however, remnants of your health data may remain in VA test databases after you leave the program.</p>', 'text', 'How to Leave', 'I understand', NULL, 'donate', '<script>\n$(function(){\n$(''#6'').css(''display'', ''none'');\n});\n</script>', '<script>$(function(){$(''#xhrIndicator_61_1'').css(''display'', ''none'');});</script>', NULL, 1, 1, '2014-09-08 17:43:54', 0),
(7, '<h1>DONATING YOUR PATIENT RECORD</h1><p>To identify your Veteran patient record, we require some information from you:</p>', 'text', 'Confirmation', 'I understand', NULL, 'donate', '<script>\n$(function(){\n$(''#7'').css(''display'', ''none'');\n});\n</script>', '<script>$(function(){$(''#data_7_1'').css(''display'', ''none'');});</script>', NULL, 1, 1, '2014-09-08 17:44:46', 0),
(8, 'I confirm that I am a VA government employee or VA Volunteer.', 'radio\r\nYes\r\nNo', NULL, NULL, 7, 'donate', NULL, NULL, NULL, 1, 1, '2014-12-30 15:29:23', 0),
(9, 'My primary VA health care facility is:', 'text', NULL, NULL, 7, 'donate', NULL, NULL, NULL, 1, 1, '2015-01-06 01:07:20', 0),
(10, 'The last 4 digits of my Social Security number are:', 'number', NULL, NULL, 7, 'donate', NULL, NULL, NULL, 1, 1, '2015-01-06 01:09:03', 0),
(11, '<h1>FINAL CONFIRMATION</h1><p>I agree to contribute my personal health data to the Donate My Data program explained above.</p>\r\n<p>I understand that if the Donate My Data program needs to contact me after I donate my record, they will use the personal contact information VA has on file for me.</p>\r\n<p>I understand that I will receive a copy of this agreement for my records.</p>\r\n<p>I understand that my health data donation agreement will begin <span class="dateToday"></span> and end <span class="dateEnd"></span>.</p>\r\n<p>I understand that I can email donatemydata@va.gov with any questions or to leave the program and VA will respond within two business days.</p>', 'text', NULL, NULL, NULL, 'donate', '<script>\r\n    $(function() {\r\n        $(''#11'').css(''display'', ''none'');\r\n        var query = [];\r\n        query[0] = {};\r\n        query[0].id = ''recordID'';\r\n        query[0].operator = ''='';\r\n        query[0].match = recordID;\r\n        $.ajax({\r\n            type: ''GET'',\r\n            url: ''api/?a=form/query&q='' + JSON.stringify(query),\r\n            dataType: ''json'',\r\n            success: function(res) {\r\n                var today = new Date(parseFloat(res[recordID].date) * 1000);\r\n                $(''.dateToday'').html(today.getMonth() + 1 + ''/'' + today.getDate() + ''/'' + today.getFullYear());\r\n                var end = new Date(today.getFullYear() + 5, today.getMonth(), today.getDate() - 1);\r\n                $(''.dateEnd'').html(end.getMonth() + 1 + ''/'' + end.getDate() + ''/'' + end.getFullYear());\r\n            }\r\n        });\r\n    });\r\n</script>', '<script>\r\n    $(function() {\r\n        $(''#data_11_1'').css(''display'', ''none'');\r\n        var query = [];\r\n        query[0] = {};\r\n        query[0].id = ''recordID'';\r\n        query[0].operator = ''='';\r\n        query[0].match = recordID;\r\n        $.ajax({\r\n            type: ''GET'',\r\n            url: ''api/?a=form/query&q='' + JSON.stringify(query),\r\n            dataType: ''json'',\r\n            success: function(res) {\r\n                var today = new Date(parseFloat(res[recordID].date) * 1000);\r\n                $(''.dateToday'').html(today.getMonth() + 1 + ''/'' + today.getDate() + ''/'' + today.getFullYear());\r\n                var end = new Date(today.getFullYear() + 5, today.getMonth(), today.getDate() - 1);\r\n                $(''.dateEnd'').html(end.getMonth() + 1 + ''/'' + end.getDate() + ''/'' + end.getFullYear());\r\n            }\r\n        });\r\n    });\r\n</script>', NULL, 0, 1, '2015-01-06 01:12:23', 0),
(12, '<p>I understand that typing my name below represents my signature and acceptance of the Donate My Data Veteran Agreement.</p>', 'text', NULL, NULL, 11, 'donate', '<script>\r\n    $(function() {\r\n        $(''#12'').after(''<span><br />Type Full Name (first name, middle name, last name)</span>'');\r\n    });\r\n</script>', NULL, NULL, 1, 1, '2015-01-06 16:27:13', 0);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `indicators`
--
ALTER TABLE `indicators`
  ADD PRIMARY KEY (`indicatorID`), ADD KEY `parentID` (`parentID`), ADD KEY `categoryID` (`categoryID`), ADD KEY `sort` (`sort`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `indicators`
--
ALTER TABLE `indicators`
  MODIFY `indicatorID` smallint(5) NOT NULL AUTO_INCREMENT,AUTO_INCREMENT=13;
--
-- Constraints for dumped tables
--

--
-- Constraints for table `indicators`
--
ALTER TABLE `indicators`
ADD CONSTRAINT `indicators_ibfk_1` FOREIGN KEY (`categoryID`) REFERENCES `categories` (`categoryID`);

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
