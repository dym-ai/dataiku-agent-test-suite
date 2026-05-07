# Upload Dataset Creation and Inspection

* **Scenario Name:** Upload and Inspect New Returns Dataset
* **Target Function:** `datasets` skill using upload dataset creation, dataset inspection, sample retrieval, and profiling
* **Sample Data (Schema & Mock Data):** Upload CSV dataset `returns_january_2026` with `return_id` (string), `order_id` (string), `return_date` (date), `return_reason` (string), `refund_amount` (double), `channel` (string)
* **Natural Language Instruction:** "Create a dataset from this January returns CSV, inspect the schema Dataiku infers, and tell me if anything looks suspicious before we start building downstream recipes."
* **Expected Dataiku Action/Output:** Creates an upload dataset from CSV content on a filesystem-capable connection, reads dataset info, fetches a sample and profile, highlights schema or quality concerns such as text-vs-date inference or skewed reasons, and leaves the dataset ready for downstream flow use.

**returns_january_2026.csv**
return_id,order_id,return_date,return_reason,refund_amount,channel
R1001,O88091,2026-01-03,Wrong size,232.05,ecommerce
R1002,O88246,2026-01-03,Wrong size,223.26,store
R1003,O88393,2026-01-03,Damaged item,235.89,ecommerce
R1004,O88389,2026-01-04,Item missing parts,137.14,store
R1005,O88277,2026-01-05,Not as described,235.98,marketplace
R1006,O88105,2026-01-06,Defective,217.96,store
R1007,O88081,2026-01-07,Damaged item,14.53,marketplace
R1008,O88102,2026-01-07,Damaged item,68.19,ecommerce
R1009,O88037,2026-01-08,Item missing parts,199.87,ecommerce
R1010,O88286,2026-01-08,Changed mind,227.14,ecommerce
R1011,O88153,2026-01-08,Damaged item,236.58,store
R1012,O88199,2026-01-08,Defective,84.29,marketplace
R1013,O88511,2026-01-08,Damaged item,64.86,marketplace
R1014,O88079,2026-01-09,Damaged item,183.94,ecommerce
R1015,O88185,2026-01-09,Damaged item,170.99,ecommerce
R1016,O88171,2026-01-10,Wrong size,153.01,ecommerce
R1017,O88083,2026-01-10,Late delivery,165.53,store
R1018,O88057,2026-01-11,Item missing parts,132.36,ecommerce
R1019,O88169,2026-01-12,Defective,53.24,marketplace
R1020,O88031,2026-01-15,Defective,116.82,marketplace
R1021,O88080,2026-01-15,Changed mind,148.03,store
R1022,O88042,2026-01-16,Defective,221.97,store
R1023,O88123,2026-01-17,Not as described,184.15,store
R1024,O88072,2026-01-20,Item missing parts,247.76,store
R1025,O88088,2026-01-21,Late delivery,176.61,ecommerce
R1026,O88146,2026-01-22,Not as described,30.25,store
R1027,O88057,2026-01-22,Changed mind,217.7,ecommerce
R1028,O88293,2026-01-22,Changed mind,59.33,store
R1029,O88213,2026-01-23,Changed mind,55.25,store
R1030,O88039,2026-01-24,Defective,249.16,ecommerce
R1031,O88361,2026-01-24,Item missing parts,221.37,store
R1032,O88373,2026-01-24,Defective,97.55,marketplace
R1033,O88025,2026-01-27,Late delivery,211.61,store
R1034,O88053,2026-01-28,Wrong size,84.52,store
R1035,O88312,2026-01-28,Wrong size,166.27,ecommerce
R1036,O88033,2026-01-29,Defective,12.0,ecommerce
R1037,O88043,2026-01-29,Changed mind,90.79,store
R1038,O88066,2026-01-29,Wrong size,177.62,store
R1039,O88336,2026-01-30,Defective,224.39,ecommerce
R1040,O88301,2026-01-30,Damaged item,106.24,store
R1041,O88177,2026-02-01,Damaged item,60.72,ecommerce
R1042,O88117,2026-02-04,Defective,71.91,marketplace
R1043,O88061,2026-02-07,Not as described,104.4,store
R1044,O88206,2026-02-07,Wrong size,212.41,marketplace
R1045,O88195,2026-02-08,Changed mind,106.07,ecommerce
R1046,O88077,2026-02-10,Defective,177.07,ecommerce
R1047,O88078,2026-02-10,Damaged item,209.29,marketplace
R1048,O88055,2026-02-11,Late delivery,161.53,marketplace
R1049,O88270,2026-02-12,Not as described,140.29,marketplace
R1050,O88141,2026-02-13,Defective,86.61,marketplace
R1051,O88162,2026-02-13,Late delivery,147.38,marketplace
R1052,O88255,2026-02-16,Not as described,164.15,ecommerce
R1053,O88047,2026-02-17,Damaged item,24.84,store
R1054,O88186,2026-02-17,Item missing parts,13.04,marketplace
R1055,O88096,2026-02-20,Damaged item,71.3,marketplace
R1056,O88240,2026-02-21,Changed mind,158.16,store
R1057,O88451,2026-02-21,Wrong size,95.01,marketplace
R1058,O88161,2026-02-22,Not as described,46.47,store
R1059,O88105,2026-02-22,Changed mind,42.92,store
R1060,O88021,2026-02-23,Late delivery,92.38,ecommerce
R1061,O88045,2026-02-25,Late delivery,193.68,store
R1062,O88181,2026-02-25,Damaged item,217.35,store
R1063,O88060,2026-02-26,Item missing parts,67.26,store
R1064,O88476,2026-02-26,Changed mind,144.91,ecommerce
R1065,O88113,2026-02-27,Defective,149.35,marketplace
R1066,O88163,2026-03-02,Wrong size,216.75,ecommerce
R1067,O88033,2026-03-03,Wrong size,173.28,store
R1068,O88121,2026-03-03,Late delivery,248.26,marketplace
R1069,O88109,2026-03-05,Damaged item,248.57,store
R1070,O88086,2026-03-07,Wrong size,161.08,marketplace
R1071,O88168,2026-03-09,Not as described,109.87,store
R1072,O88331,2026-03-10,Changed mind,191.98,ecommerce
R1073,O88205,2026-03-12,Late delivery,43.1,ecommerce
R1074,O88098,2026-03-13,Item missing parts,65.5,ecommerce
R1075,O88087,2026-03-15,Changed mind,157.96,marketplace
R1076,O88056,2026-03-16,Wrong size,87.03,store
R1077,O88431,2026-03-18,Wrong size,213.98,ecommerce
R1078,O88401,2026-03-18,Late delivery,229.12,marketplace
R1079,O88249,2026-03-19,Changed mind,22.49,ecommerce
R1080,O88101,2026-03-19,Item missing parts,16.86,marketplace
R1081,O88291,2026-03-19,Late delivery,12.21,marketplace
R1082,O88057,2026-03-20,Late delivery,174.81,ecommerce
R1083,O88201,2026-03-20,Changed mind,161.86,marketplace
R1084,O88065,2026-03-21,Not as described,101.52,marketplace
R1085,O88082,2026-03-23,Changed mind,168.94,store
R1086,O88047,2026-03-24,Late delivery,196.97,store
R1087,O88093,2026-03-24,Late delivery,191.81,marketplace
R1088,O88516,2026-03-24,Defective,71.6,ecommerce
R1089,O88022,2026-03-25,Not as described,220.49,marketplace
R1090,O88192,2026-03-26,Wrong size,236.79,marketplace
R1091,O88129,2026-03-28,Changed mind,245.45,store
R1092,O88258,2026-03-28,Late delivery,182.49,ecommerce
R1093,O88097,2026-03-29,Not as described,144.93,ecommerce
R1094,O88075,2026-03-31,Changed mind,110.64,store
R1095,O88133,2026-03-31,Defective,142.49,marketplace
R1096,O88253,2026-03-31,Wrong size,117.64,marketplace
R1097,O88117,2026-03-31,Changed mind,248.57,ecommerce
R1098,O88150,2026-04-01,Not as described,23.67,marketplace
R1099,O88228,2026-04-01,Damaged item,28.96,ecommerce
R1100,O88397,2026-04-01,Not as described,103.59,store