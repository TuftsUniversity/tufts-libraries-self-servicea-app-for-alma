    SELECT 
        "Bibliographic Details"."MMS Id" saw_0, 
        "Physical Item Details"."Barcode" saw_1, 
        "Holding Details"."Permanent Call Number" saw_2,
		"Physical Item Details"."Description" saw_3,
		"Location"."Location Name" saw_4,
		"Physical Item Details"."Base Status" saw_5,
		"Physical Item Details"."Process Type" saw_6, 
		Evaluate('Regexp_substr(%1,''\(OC.?LC\)\s*(\d+)'',1,1,''i'',1)',"Bibliographic Details"."Local Param 09") Related_OCLC
		
    FROM "Physical Items" 
    WHERE "Physical Item Details"."Lifecycle" <> 'Deleted' AND  "Physical Item Details"."Lifecycle" <> 'Withdrawn'  
) physical_items ON cr.MMS_Id = physical_items.MMS_Id OR cr.OCLC = physical_items.Related_OCLC