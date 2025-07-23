 FROM (
    SELECT 
        "Course"."Processing Department" saw_0, 
        "Course"."Course Code" saw_1, 
        "Course"."Course Name" saw_2, 
        "Reading List"."Reading List Name" saw_3, 
        "Reading List Citation"."Citation Create Date" saw_4, 
        LEFT("Bibliographic Details"."Title", 150) AS saw_5, 
        "Bibliographic Details"."MMS Id" saw_6, 
		"Bibliographic Details"."OCLC Control Number (035a)" saw_7, 
        "Reading List Citation"."Citation Status" saw_8, 
        "Reading List Citation"."Citation Type" saw_9,
		"Reading List Citations"."Citation Source" saw_10
    FROM "Course Reserves"
WHERE
(("Reading List Citation"."Citation Create Date" >= TIMESTAMPADD(SQL_TSI_DAY,-30,CURRENT_DATE)) AND ("Course"."Processing Department" = 'Music Reserves'))