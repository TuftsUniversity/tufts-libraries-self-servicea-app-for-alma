SELECT 
   cr.Processing_Department,
   cr.Course_Code,
   cr.Course_Name,
   cr.Reading_List_Name,
   cr.Title,
   cr.Citation_Source,
   physical_items.Barcode,
   physical_items.Permanent_Call_Number,
   physical_items.Description,
   physical_items.Temporary_Physical_Location, 
   physical_items.Permanent_Location,
   physical_items.Base_Status,
   physical_items.Process_Type,
   cr.Citation_Creation_Date,
   cr.MMS_Id,
   cr.Citation_Status,
   cr.Citation_Type
 FROM (
    SELECT 
        "Course"."Processing Department" Processing_Department, 
        "Course"."Course Code" Course_Code, 
        "Course"."Course Name" Course_Name, 
        "Reading List"."Reading List Name" Reading_List_Name, 
        "Reading List Citation"."Citation Create Date" Citation_Creation_Date, 
        LEFT("Bibliographic Details"."Title", 150) AS Title, 
        "Bibliographic Details"."MMS Id" MMS_Id, 
		"Bibliographic Details"."OCLC Control Number (035a)" OCLC, 
        "Reading List Citation"."Citation Status" Citation_Status, 
        "Reading List Citation"."Citation Type" Citation_Type,
		"Reading List Citations"."Citation Source" Citation_Source
    FROM "Course Reserves"
WHERE
(("Reading List Citation"."Citation Create Date" >= TIMESTAMPADD(SQL_TSI_DAY,-30,CURRENT_DATE)) AND ("Course"."Processing Department" = 'Music Reserves'))
) cr LEFT JOIN (
    SELECT 
        "Bibliographic Details"."MMS Id" MMS_Id, 
        "Physical Item Details"."Barcode" Barcode, 
        "Holding Details"."Permanent Call Number" Permanent_Call_Number,
		"Physical Item Details"."Description" Description,
		"Location"."Location Name" Permanent_Location,
		CASE WHEN "Temporary Location"."Temporary Location Name" IS NOT NULL AND "Physical Item Details"."Temporary Physical Location In Use" = 'Yes' THEN "Temporary Location"."Temporary Location Name" ELSE '' END Temporary_Physical_Location, 
		"Physical Item Details"."Base Status" Base_Status,
		"Physical Item Details"."Process Type" Process_Type, 
		Evaluate('Regexp_substr(%1,''\(OC.?LC\)\s*(\d+)'',1,1,''i'',1)',"Bibliographic Details"."Local Param 09") Related_OCLC
		
    FROM "Physical Items" 
    WHERE "Physical Item Details"."Lifecycle" <> 'Deleted' AND  "Physical Item Details"."Lifecycle" <> 'Withdrawn'  
) physical_items ON cr.MMS_Id = physical_items.MMS_Id OR cr.OCLC = physical_items.Related_OCLC
