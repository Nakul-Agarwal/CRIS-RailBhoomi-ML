/*=========================================================
Rail Bhoomi Prediction System
Master Dataset - Production Version

Author : Nakul Agarwal
Organization : CRIS

Business Rule:
Use official business milestone columns.
Do NOT depend on currently populated data.
=========================================================*/

WITH AllocationBase AS
(
    SELECT DISTINCT
        uwid,
        PROJECTID,
        ShortNameofWork,
        railway,
        division,
        exec_agency_rly,
        states,
        districts,
        land_acq_status
    FROM AllocationWise
),

ProjectBase AS
(
    SELECT
        pb.project_id,
        pb.project_name,
        ab.uwid,
        pb.pink_book_ref,

        ab.PROJECTID AS allocation_project_id,

        ab.ShortNameofWork,
        ab.railway,
        ab.division,
        ab.exec_agency_rly,
        ab.states,
        ab.districts,
        ab.land_acq_status,

        pb.government_land,
        pb.private_land,
        pb.forest_area,
        pb.total_land,
        pb.land_available,
        pb.land_to_be_acquired,

        pb.state_id,
        pb.status

    FROM project_basic pb

    LEFT JOIN AllocationBase ab
        ON pb.pink_book_ref = ab.PROJECTID
),

Stage37A AS
(
    SELECT
        project_id,
        CAST(MIN(publish_date) AS DATE) AS date_37A
    FROM notification_37A
    WHERE publish_date IS NOT NULL
    GROUP BY project_id
),

Stage7A AS
(
    SELECT
        project_id,
        CAST(MIN(publish_date) AS DATE) AS date_7A
    FROM la_notification_master
    WHERE publish_date IS NOT NULL
    GROUP BY project_id
),

Stage20A AS
(
    SELECT
        project_id,
        CAST(MIN(publish_date) AS DATE) AS date_20A
    FROM three_A_master
    WHERE publish_date IS NOT NULL
    GROUP BY project_id
),
Stage20E AS
(
    SELECT
        project_id,
        CAST(MIN(publish_date) AS DATE) AS date_20E
    FROM three_d_master
    WHERE publish_date IS NOT NULL
    GROUP BY project_id
),

Stage20F AS
(
    SELECT
        project_id,
        CAST(MIN(approval_date) AS DATE) AS date_20F
    FROM nhai_award
    WHERE approval_date IS NOT NULL
    GROUP BY project_id
),

Stage20H AS
(
    SELECT
        na.project_id,
        CAST(MIN(nad.payment_date) AS DATE) AS date_20H
    FROM nhai_award na
    INNER JOIN nhai_award_det nad
        ON na.award_id = nad.award_id
    WHERE nad.payment_date IS NOT NULL
    GROUP BY na.project_id
),

StageMutation AS
(
    SELECT
        na.project_id,
        CAST(MIN(nad.mutation_date) AS DATE) AS mutation_date
    FROM nhai_award na
    INNER JOIN nhai_award_det nad
        ON na.award_id = nad.award_id
    WHERE nad.mutation_date IS NOT NULL
    GROUP BY na.project_id
),
CourtCaseSummary AS
(
    SELECT

        cc.project_id,

        COUNT(DISTINCT cc.case_id) AS court_case_count,

        SUM(
            CASE
                WHEN cc.status = 'Active' THEN 1
                ELSE 0
            END
        ) AS active_court_cases,

        CAST(MIN(cc.from_date) AS DATE) AS first_court_case_date,

        CAST(MAX(cc.to_date) AS DATE) AS last_court_case_date,

        SUM(ISNULL(ccd.area,0)) AS total_disputed_area,

        COUNT(DISTINCT ccd.survey_id) AS disputed_surveys

    FROM court_case cc

    LEFT JOIN court_case_details ccd
        ON cc.case_id = ccd.case_id

    GROUP BY cc.project_id
),
ObjectionSummary AS
(
    SELECT

        tao.project_id,

        COUNT(DISTINCT tao.objection_id) AS objection_count,

        SUM(
            CASE
                WHEN tao.status = 'Active'
                THEN 1
                ELSE 0
            END
        ) AS active_objections,

        CAST(MIN(tao.objection_date) AS DATE) AS first_objection_date,

        CAST(MAX(tao.objection_date) AS DATE) AS latest_objection_date,

        COUNT(DISTINCT tao.survey_id) AS affected_surveys,

        COUNT(DISTINCT tao.party_id) AS affected_parties

    FROM three_A_objections tao

    GROUP BY
        tao.project_id
)
SELECT
    pb.uwid,
    pb.project_id,
    pb.project_name,
    pb.allocation_project_id,

    pb.ShortNameofWork,
    pb.railway,
    pb.division,
    pb.exec_agency_rly,

    pb.states,
    pb.districts,
    pb.land_acq_status,

    pb.government_land,
    pb.private_land,
    pb.forest_area,
    pb.total_land,
    pb.land_available,
    pb.land_to_be_acquired,

    pb.state_id,
    pb.status,

        s37.date_37A,
    s7.date_7A,
    s20A.date_20A,
    s20E.date_20E,
    s20F.date_20F,
    s20H.date_20H,
    sm.mutation_date,

ISNULL(cc.court_case_count,0) AS court_case_count,
ISNULL(cc.active_court_cases,0) AS active_court_cases,
cc.first_court_case_date,
cc.last_court_case_date,
ISNULL(cc.total_disputed_area,0) AS total_disputed_area,
ISNULL(cc.disputed_surveys,0) AS disputed_surveys,

ISNULL(obj.objection_count,0) AS objection_count,
ISNULL(obj.active_objections,0) AS active_objections,
obj.first_objection_date,
obj.latest_objection_date,
ISNULL(obj.affected_surveys,0) AS affected_surveys,
ISNULL(obj.affected_parties,0) AS affected_parties


FROM ProjectBase pb

LEFT JOIN Stage37A s37
    ON pb.project_id = s37.project_id

LEFT JOIN Stage7A s7
    ON pb.project_id = s7.project_id

LEFT JOIN Stage20A s20A
    ON pb.project_id = s20A.project_id

LEFT JOIN Stage20E s20E
    ON pb.project_id = s20E.project_id

LEFT JOIN Stage20F s20F
    ON pb.project_id = s20F.project_id

LEFT JOIN Stage20H s20H
    ON pb.project_id = s20H.project_id
LEFT JOIN StageMutation sm
    ON pb.project_id = sm.project_id

LEFT JOIN CourtCaseSummary cc
    ON pb.project_id = cc.project_id

LEFT JOIN ObjectionSummary obj
    ON pb.project_id = obj.project_id

ORDER BY pb.project_id;

