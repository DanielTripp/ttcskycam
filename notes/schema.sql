--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET client_encoding = 'SQL_ASCII';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

SET search_path = public, pg_catalog;

--
-- Name: printf(text, anyarray); Type: FUNCTION; Schema: public; Owner: dt
--

CREATE FUNCTION printf(fmt text, VARIADIC args anyarray) RETURNS text
    LANGUAGE plpgsql
    AS $$
        DECLARE
                argcnt  int = 1;
                chrcnt  int = 0;
                fmtlen  int;
                CHR             text;
                output  text = '';
        BEGIN
                fmtlen = LENGTH(fmt);
                LOOP
                        chrcnt = chrcnt + 1;
 
                        -- ran out of format string? bail out
                        IF chrcnt > fmtlen THEN
                                EXIT;
                        END IF;
 
                        -- grab our char
                        CHR = substring(fmt, chrcnt, 1);
 
                        -- %% means output a single %, and skip them
                        IF CHR = '%' AND substring(fmt, chrcnt + 1, 1) = '%' THEN
                                output = output || '%';
                                chrcnt = chrcnt + 1;
                                continue;
                        END IF;
 
                        -- a % on its own means output an element from our arg list
                        IF CHR = '%' THEN
                                output = output || COALESCE(args[argcnt]::text, '');
                                argcnt = argcnt + 1;
                                continue;
                        END IF;
 
                        -- no special case? output the thing
                        output = output || CHR;
                END LOOP;
 
                RETURN output;
        END;
$$;


ALTER FUNCTION public.printf(fmt text, VARIADIC args anyarray) OWNER TO dt;

--
-- Name: %%; Type: OPERATOR; Schema: public; Owner: postgres
--

CREATE OPERATOR %% (
    PROCEDURE = pst.format_op,
    LEFTARG = text,
    RIGHTARG = "any"
);


ALTER OPERATOR public.%% (text, "any") OWNER TO postgres;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: predictions; Type: TABLE; Schema: public; Owner: dt; Tablespace: 
--

CREATE TABLE predictions (
    fudgeroute character varying(100),
    configroute character varying(100),
    stoptag character varying(100),
    time_retrieved_str character varying(30),
    time_of_prediction_str character varying(30),
    dirtag character varying(100),
    vehicle_id character varying(100),
    is_departure boolean,
    block character varying(100),
    triptag character varying(100),
    branch character varying(100),
    affected_by_layover boolean,
    is_schedule_based boolean,
    delayed boolean,
    time_retrieved bigint,
    time_of_prediction bigint,
    rowid integer NOT NULL
);


ALTER TABLE public.predictions OWNER TO dt;

--
-- Name: predictions_rowid_seq; Type: SEQUENCE; Schema: public; Owner: dt
--

CREATE SEQUENCE predictions_rowid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.predictions_rowid_seq OWNER TO dt;

--
-- Name: predictions_rowid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: dt
--

ALTER SEQUENCE predictions_rowid_seq OWNED BY predictions.rowid;


--
-- Name: reports; Type: TABLE; Schema: public; Owner: dt; Tablespace: 
--

CREATE TABLE reports (
    app_version character varying(20),
    report_type character varying(20),
    froute character varying(100),
    direction integer,
    datazoom integer,
    "time" bigint,
    timestr character varying(30),
    time_inserted_str character varying(30),
    report_json text
);


ALTER TABLE public.reports OWNER TO dt;

--
-- Name: test; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE test (
    i integer,
    s character varying(10)
);


ALTER TABLE public.test OWNER TO postgres;

--
-- Name: ttc_vehicle_locations; Type: TABLE; Schema: public; Owner: dt; Tablespace: 
--

CREATE TABLE ttc_vehicle_locations (
    vehicle_id character varying(100),
    fudgeroute character varying(20),
    route_tag character varying(10),
    dir_tag character varying(100),
    lat double precision,
    lon double precision,
    secs_since_report integer,
    time_retrieved bigint,
    predictable boolean,
    heading integer,
    "time" bigint,
    time_str character varying(100),
    rowid integer NOT NULL,
    mofr integer,
    widemofr integer,
    graph_locs character varying(1000),
    graph_version integer,
    froute_version integer NOT NULL
);


ALTER TABLE public.ttc_vehicle_locations OWNER TO dt;

--
-- Name: ttc_vehicle_locations_rowid_seq; Type: SEQUENCE; Schema: public; Owner: dt
--

CREATE SEQUENCE ttc_vehicle_locations_rowid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ttc_vehicle_locations_rowid_seq OWNER TO dt;

--
-- Name: ttc_vehicle_locations_rowid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: dt
--

ALTER SEQUENCE ttc_vehicle_locations_rowid_seq OWNED BY ttc_vehicle_locations.rowid;


--
-- Name: rowid; Type: DEFAULT; Schema: public; Owner: dt
--

ALTER TABLE ONLY predictions ALTER COLUMN rowid SET DEFAULT nextval('predictions_rowid_seq'::regclass);


--
-- Name: rowid; Type: DEFAULT; Schema: public; Owner: dt
--

ALTER TABLE ONLY ttc_vehicle_locations ALTER COLUMN rowid SET DEFAULT nextval('ttc_vehicle_locations_rowid_seq'::regclass);


--
-- Name: predictions_rowid_key; Type: CONSTRAINT; Schema: public; Owner: dt; Tablespace: 
--

ALTER TABLE ONLY predictions
    ADD CONSTRAINT predictions_rowid_key UNIQUE (rowid);


--
-- Name: ttc_vehicle_locations_rowid_key; Type: CONSTRAINT; Schema: public; Owner: dt; Tablespace: 
--

ALTER TABLE ONLY ttc_vehicle_locations
    ADD CONSTRAINT ttc_vehicle_locations_rowid_key UNIQUE (rowid);


--
-- Name: predictions_idx; Type: INDEX; Schema: public; Owner: dt; Tablespace: 
--

CREATE INDEX predictions_idx ON predictions USING btree (fudgeroute, stoptag, time_retrieved DESC);


--
-- Name: predictions_idx2; Type: INDEX; Schema: public; Owner: dt; Tablespace: 
--

CREATE INDEX predictions_idx2 ON predictions USING btree (time_retrieved);


--
-- Name: reports_idx; Type: INDEX; Schema: public; Owner: dt; Tablespace: 
--

CREATE INDEX reports_idx ON reports USING btree (app_version, report_type, froute, direction, datazoom, "time" DESC);


--
-- Name: reports_idx_3; Type: INDEX; Schema: public; Owner: dt; Tablespace: 
--

CREATE INDEX reports_idx_3 ON reports USING btree ("time" DESC, time_inserted_str DESC);


--
-- Name: ttc_vehicle_locations_idx; Type: INDEX; Schema: public; Owner: dt; Tablespace: 
--

CREATE INDEX ttc_vehicle_locations_idx ON ttc_vehicle_locations USING btree (fudgeroute, time_retrieved DESC);


--
-- Name: ttc_vehicle_locations_idx2; Type: INDEX; Schema: public; Owner: dt; Tablespace: 
--

CREATE INDEX ttc_vehicle_locations_idx2 ON ttc_vehicle_locations USING btree (vehicle_id, time_retrieved DESC);


--
-- Name: ttc_vehicle_locations_idx3; Type: INDEX; Schema: public; Owner: dt; Tablespace: 
--

CREATE INDEX ttc_vehicle_locations_idx3 ON ttc_vehicle_locations USING btree (time_retrieved);


--
-- Name: public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

