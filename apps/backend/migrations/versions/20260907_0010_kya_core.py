# ruff: noqa: E501
"""Create the canonical KYA Core master-data schema.

Revision ID: 20260907_0010
Revises: 20260907_0009
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260907_0010"
down_revision: str | None = "20260907_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_DDL = (
    "CREATE TABLE core.external_reference (\n\tid UUID NOT NULL, \n\tsystem_key VARCHAR(120) NOT NULL, \n\tentity_type VARCHAR(80) NOT NULL, \n\tentity_id UUID NOT NULL, \n\texternal_type VARCHAR(120) NOT NULL, \n\texternal_id VARCHAR(500) NOT NULL, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_external_reference PRIMARY KEY (id), \n\tCONSTRAINT uq_core_external_reference UNIQUE (system_key, entity_type, external_type, external_id)\n)",
    "CREATE TABLE core.organizational_unit_type (\n\tkey VARCHAR(80) NOT NULL, \n\tlabel VARCHAR(120) NOT NULL, \n\tallowed_parent_types VARCHAR(80)[] NOT NULL, \n\tis_temporary BOOLEAN NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tCONSTRAINT pk_organizational_unit_type PRIMARY KEY (key), \n\tCONSTRAINT ck_organizational_unit_type_valid_status CHECK (status IN ('active', 'inactive', 'archived'))\n)",
    "CREATE TABLE core.party (\n\tid UUID NOT NULL, \n\tkind VARCHAR(32) NOT NULL, \n\tdisplay_name VARCHAR(240) NOT NULL, \n\tlegal_name VARCHAR(240), \n\tstatus VARCHAR(32) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_party PRIMARY KEY (id), \n\tCONSTRAINT ck_party_valid_kind CHECK (kind IN ('person', 'organization')), \n\tCONSTRAINT ck_party_valid_status CHECK (status IN ('active', 'inactive', 'archived')), \n\tCONSTRAINT ck_party_positive_version CHECK (version > 0)\n)",
    "CREATE TABLE core.contact_point (\n\tid UUID NOT NULL, \n\tparty_id UUID NOT NULL, \n\tkind VARCHAR(32) NOT NULL, \n\tlabel VARCHAR(80), \n\tvalue VARCHAR(500) NOT NULL, \n\tnormalized_value VARCHAR(500) NOT NULL, \n\tis_primary BOOLEAN NOT NULL, \n\tclassification VARCHAR(32) NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tcreated_by UUID NOT NULL, \n\tCONSTRAINT pk_contact_point PRIMARY KEY (id), \n\tCONSTRAINT uq_core_contact_point_value UNIQUE (party_id, kind, normalized_value), \n\tCONSTRAINT ck_contact_point_valid_kind CHECK (kind IN ('email', 'phone', 'address', 'url')), \n\tCONSTRAINT ck_contact_point_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT fk_contact_point_party_id_party FOREIGN KEY(party_id) REFERENCES core.party (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.organizational_unit (\n\tid UUID NOT NULL, \n\tkey VARCHAR(120) NOT NULL, \n\ttype_key VARCHAR(80) NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\tlegal_name VARCHAR(240), \n\tcountry_code VARCHAR(2), \n\tstatus VARCHAR(32) NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tversion INTEGER NOT NULL, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_organizational_unit PRIMARY KEY (id), \n\tCONSTRAINT uq_core_organizational_unit_key UNIQUE (key), \n\tCONSTRAINT ck_organizational_unit_valid_status CHECK (status IN ('active', 'inactive', 'archived')), \n\tCONSTRAINT ck_organizational_unit_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT ck_organizational_unit_positive_version CHECK (version > 0), \n\tCONSTRAINT fk_organizational_unit_type_key_organizational_unit_type FOREIGN KEY(type_key) REFERENCES core.organizational_unit_type (key) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.person_profile (\n\tparty_id UUID NOT NULL, \n\tgiven_name VARCHAR(120) NOT NULL, \n\tfamily_name VARCHAR(120) NOT NULL, \n\tpreferred_name VARCHAR(120), \n\tCONSTRAINT pk_person_profile PRIMARY KEY (party_id), \n\tCONSTRAINT fk_person_profile_party_id_party FOREIGN KEY(party_id) REFERENCES core.party (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.client_account (\n\tid UUID NOT NULL, \n\tkey VARCHAR(120) NOT NULL, \n\tparty_id UUID NOT NULL, \n\towner_unit_id UUID NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tversion INTEGER NOT NULL, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_client_account PRIMARY KEY (id), \n\tCONSTRAINT uq_core_client_account_key UNIQUE (key), \n\tCONSTRAINT ck_client_account_valid_status CHECK (status IN ('prospect', 'active', 'suspended', 'inactive', 'archived')), \n\tCONSTRAINT ck_client_account_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT ck_client_account_positive_version CHECK (version > 0), \n\tCONSTRAINT uq_client_account_party_id UNIQUE (party_id), \n\tCONSTRAINT fk_client_account_party_id_party FOREIGN KEY(party_id) REFERENCES core.party (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_client_account_owner_unit_id_organizational_unit FOREIGN KEY(owner_unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.organizational_unit_relation (\n\tid UUID NOT NULL, \n\tparent_unit_id UUID NOT NULL, \n\tchild_unit_id UUID NOT NULL, \n\tkind VARCHAR(32) NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_organizational_unit_relation PRIMARY KEY (id), \n\tCONSTRAINT ck_organizational_unit_relation_different_units CHECK (parent_unit_id <> child_unit_id), \n\tCONSTRAINT ck_organizational_unit_relation_valid_kind CHECK (kind IN ('hierarchical', 'transversal')), \n\tCONSTRAINT ck_organizational_unit_relation_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT fk_organizational_unit_relation_parent_unit_id_organiza_3252 FOREIGN KEY(parent_unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_organizational_unit_relation_child_unit_id_organizat_9fcc FOREIGN KEY(child_unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.position (\n\tid UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tkey VARCHAR(120) NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tcreated_by UUID NOT NULL, \n\tCONSTRAINT pk_position PRIMARY KEY (id), \n\tCONSTRAINT uq_core_position_unit_key UNIQUE (unit_id, key), \n\tCONSTRAINT ck_position_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT fk_position_unit_id_organizational_unit FOREIGN KEY(unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.site (\n\tid UUID NOT NULL, \n\tkey VARCHAR(120) NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\towner_unit_id UUID NOT NULL, \n\towner_party_id UUID NOT NULL, \n\tcountry_code VARCHAR(2) NOT NULL, \n\tlocality VARCHAR(240), \n\taddress JSONB, \n\tstatus VARCHAR(32) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_site PRIMARY KEY (id), \n\tCONSTRAINT uq_core_site_key UNIQUE (key), \n\tCONSTRAINT ck_site_valid_status CHECK (status IN ('active', 'inactive', 'archived')), \n\tCONSTRAINT ck_site_valid_country_code CHECK (country_code ~ '^[A-Z]{2}$'), \n\tCONSTRAINT ck_site_positive_version CHECK (version > 0), \n\tCONSTRAINT fk_site_owner_unit_id_organizational_unit FOREIGN KEY(owner_unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_site_owner_party_id_party FOREIGN KEY(owner_party_id) REFERENCES core.party (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.work_relationship (\n\tid UUID NOT NULL, \n\tperson_id UUID NOT NULL, \n\temployer_unit_id UUID NOT NULL, \n\tprincipal_id UUID, \n\tkind VARCHAR(32) NOT NULL, \n\tpersonnel_number VARCHAR(80), \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tcreated_by UUID NOT NULL, \n\tCONSTRAINT pk_work_relationship PRIMARY KEY (id), \n\tCONSTRAINT ck_work_relationship_valid_kind CHECK (kind IN ('employee', 'intern', 'contractor', 'consultant')), \n\tCONSTRAINT ck_work_relationship_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT fk_work_relationship_person_id_party FOREIGN KEY(person_id) REFERENCES core.party (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_work_relationship_employer_unit_id_organizational_unit FOREIGN KEY(employer_unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.position_assignment (\n\tid UUID NOT NULL, \n\tperson_id UUID NOT NULL, \n\tposition_id UUID NOT NULL, \n\tscope_unit_id UUID NOT NULL, \n\tkind VARCHAR(32) NOT NULL, \n\tallocation_percent INTEGER, \n\treports_to_assignment_id UUID, \n\tdelegated_by_principal_id UUID, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tcreated_by UUID NOT NULL, \n\tCONSTRAINT pk_position_assignment PRIMARY KEY (id), \n\tCONSTRAINT ck_position_assignment_valid_kind CHECK (kind IN ('primary', 'secondary', 'acting', 'delegation')), \n\tCONSTRAINT ck_position_assignment_valid_allocation CHECK (allocation_percent IS NULL OR allocation_percent BETWEEN 1 AND 100), \n\tCONSTRAINT ck_position_assignment_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT fk_position_assignment_person_id_party FOREIGN KEY(person_id) REFERENCES core.party (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_position_assignment_position_id_position FOREIGN KEY(position_id) REFERENCES core.position (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_position_assignment_scope_unit_id_organizational_unit FOREIGN KEY(scope_unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_position_assignment_reports_to_assignment_id_positio_3d19 FOREIGN KEY(reports_to_assignment_id) REFERENCES core.position_assignment (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.project (\n\tid UUID NOT NULL, \n\tkey VARCHAR(120) NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\towner_unit_id UUID NOT NULL, \n\tclient_id UUID, \n\tstatus VARCHAR(32) NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_until TIMESTAMP WITH TIME ZONE, \n\tversion INTEGER NOT NULL, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_project PRIMARY KEY (id), \n\tCONSTRAINT uq_core_project_key UNIQUE (key), \n\tCONSTRAINT ck_project_valid_status CHECK (status IN ('planned', 'active', 'on_hold', 'completed', 'cancelled', 'archived')), \n\tCONSTRAINT ck_project_valid_business_period CHECK (valid_until IS NULL OR valid_until > valid_from), \n\tCONSTRAINT ck_project_positive_version CHECK (version > 0), \n\tCONSTRAINT fk_project_owner_unit_id_organizational_unit FOREIGN KEY(owner_unit_id) REFERENCES core.organizational_unit (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_project_client_id_client_account FOREIGN KEY(client_id) REFERENCES core.client_account (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE core.project_site (\n\tproject_id UUID NOT NULL, \n\tsite_id UUID NOT NULL, \n\tcreated_by UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_project_site PRIMARY KEY (project_id, site_id), \n\tCONSTRAINT fk_project_site_project_id_project FOREIGN KEY(project_id) REFERENCES core.project (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_project_site_site_id_site FOREIGN KEY(site_id) REFERENCES core.site (id) ON DELETE RESTRICT\n)",
    "CREATE INDEX ix_core_external_reference_entity ON core.external_reference (entity_type, entity_id)",
    "CREATE INDEX ix_core_party_display_name ON core.party (display_name)",
    "CREATE INDEX ix_core_contact_point_party ON core.contact_point (party_id)",
    "CREATE INDEX ix_core_organizational_unit_type ON core.organizational_unit (type_key)",
    "CREATE INDEX ix_core_client_owner ON core.client_account (owner_unit_id, status)",
    "CREATE INDEX ix_core_unit_relation_child ON core.organizational_unit_relation (child_unit_id, kind)",
    "CREATE INDEX ix_core_unit_relation_parent ON core.organizational_unit_relation (parent_unit_id, kind)",
    "CREATE INDEX ix_core_site_owner ON core.site (owner_unit_id)",
    "CREATE INDEX ix_core_work_relationship_principal ON core.work_relationship (principal_id)",
    "CREATE INDEX ix_core_work_relationship_person ON core.work_relationship (person_id)",
    "CREATE INDEX ix_core_position_assignment_person ON core.position_assignment (person_id)",
    "CREATE INDEX ix_core_project_owner ON core.project (owner_unit_id, status)",
)
DOWNGRADE_DDL = (
    'DROP TABLE IF EXISTS core."project_site" CASCADE',
    'DROP TABLE IF EXISTS core."project" CASCADE',
    'DROP TABLE IF EXISTS core."position_assignment" CASCADE',
    'DROP TABLE IF EXISTS core."work_relationship" CASCADE',
    'DROP TABLE IF EXISTS core."site" CASCADE',
    'DROP TABLE IF EXISTS core."position" CASCADE',
    'DROP TABLE IF EXISTS core."organizational_unit_relation" CASCADE',
    'DROP TABLE IF EXISTS core."client_account" CASCADE',
    'DROP TABLE IF EXISTS core."person_profile" CASCADE',
    'DROP TABLE IF EXISTS core."organizational_unit" CASCADE',
    'DROP TABLE IF EXISTS core."contact_point" CASCADE',
    'DROP TABLE IF EXISTS core."party" CASCADE',
    'DROP TABLE IF EXISTS core."organizational_unit_type" CASCADE',
    'DROP TABLE IF EXISTS core."external_reference" CASCADE',
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS core")
    for statement in UPGRADE_DDL:
        op.execute(statement)
    op.execute(
        """
        INSERT INTO core.organizational_unit_type
            (key, label, allowed_parent_types, is_temporary, status)
        VALUES
            ('group', 'Groupe', ARRAY[]::varchar[], false, 'active'),
            ('country', 'Pays', ARRAY['group']::varchar[], false, 'active'),
            ('entity', 'Entité', ARRAY['group', 'country']::varchar[], false, 'active'),
            ('agency', 'Agence', ARRAY['country', 'entity']::varchar[], false, 'active'),
            ('direction', 'Direction', ARRAY['group', 'country', 'entity', 'agency']::varchar[], false, 'active'),
            ('department', 'Département', ARRAY['direction']::varchar[], false, 'active'),
            ('team', 'Équipe', ARRAY['direction', 'department']::varchar[], false, 'active'),
            ('program', 'Programme', ARRAY['group', 'country', 'entity', 'direction']::varchar[], true, 'active'),
            ('project', 'Équipe projet', ARRAY['program', 'direction', 'department', 'team']::varchar[], true, 'active'),
            ('community', 'Communauté', ARRAY['group', 'country', 'entity', 'direction', 'department', 'team']::varchar[], true, 'active')
        """
    )
    op.execute(
        """
        INSERT INTO core.organizational_unit
            (id, key, type_key, name, legal_name, country_code, status,
             valid_from, valid_until, version, created_by)
        VALUES
            ('01993450-0000-7000-8000-000000000001', 'group', 'group',
             'KYA-Energy Group', 'KYA-Energy Group', NULL, 'active',
             '2026-01-01T00:00:00Z', NULL, 1,
             '01993450-0000-7000-8000-000000000000')
        """
    )
    op.execute(
        """
        CREATE FUNCTION core.validate_hierarchical_unit_relation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          parent_type varchar;
          child_allowed_parents varchar[];
          new_period tstzrange;
        BEGIN
          IF NEW.kind <> 'hierarchical' THEN
            RETURN NEW;
          END IF;

          SELECT type_key INTO parent_type
          FROM core.organizational_unit WHERE id = NEW.parent_unit_id;

          SELECT unit_type.allowed_parent_types INTO child_allowed_parents
          FROM core.organizational_unit child
          JOIN core.organizational_unit_type unit_type ON unit_type.key = child.type_key
          WHERE child.id = NEW.child_unit_id;

          IF parent_type IS NULL OR child_allowed_parents IS NULL
             OR NOT parent_type = ANY(child_allowed_parents) THEN
            RAISE EXCEPTION 'organizational unit parent type is not allowed';
          END IF;

          new_period := tstzrange(NEW.valid_from, NEW.valid_until, '[)');
          IF EXISTS (
            WITH RECURSIVE reachable(unit_id, active_period) AS (
              SELECT relation.child_unit_id,
                     tstzrange(relation.valid_from, relation.valid_until, '[)') * new_period
              FROM core.organizational_unit_relation relation
              WHERE relation.kind = 'hierarchical'
                AND relation.parent_unit_id = NEW.child_unit_id
                AND tstzrange(relation.valid_from, relation.valid_until, '[)') && new_period
              UNION ALL
              SELECT relation.child_unit_id,
                     tstzrange(relation.valid_from, relation.valid_until, '[)') * reachable.active_period
              FROM reachable
              JOIN core.organizational_unit_relation relation
                ON relation.parent_unit_id = reachable.unit_id
              WHERE relation.kind = 'hierarchical'
                AND tstzrange(relation.valid_from, relation.valid_until, '[)')
                    && reachable.active_period
            )
            SELECT 1 FROM reachable WHERE unit_id = NEW.parent_unit_id
          ) THEN
            RAISE EXCEPTION 'hierarchical organizational relations contain a cycle';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_core_validate_hierarchical_unit_relation
        BEFORE INSERT OR UPDATE ON core.organizational_unit_relation
        FOR EACH ROW EXECUTE FUNCTION core.validate_hierarchical_unit_relation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_core_validate_hierarchical_unit_relation "
        "ON core.organizational_unit_relation"
    )
    op.execute("DROP FUNCTION IF EXISTS core.validate_hierarchical_unit_relation()")
    for statement in DOWNGRADE_DDL:
        op.execute(statement)
    op.execute("DROP SCHEMA IF EXISTS core")
