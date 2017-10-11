import logging
import time
from datetime import datetime
import uuid
from airflow.plugins_manager import AirflowPlugin
from airflow.utils.decorators import apply_defaults
from airflow.operators import BaseOperator
from airflow.contrib.hooks.gcp_api_base_hook import GoogleCloudBaseHook
from airflow.hooks.dbapi_hook import DbApiHook
from bigquery import get_client
from bigquery.errors import BigQueryTimeoutException


#silence some annoying warnings
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

#set logging level for the plugin
logging.getLogger(__name__).setLevel(logging.INFO)

class BigQueryHook(GoogleCloudBaseHook, DbApiHook):

    """
    Interact with BigQuery. This hook uses the Google Cloud Platform
    connection.
    """
    conn_name_attr = 'bigquery_conn_id'

    def __init__(self,
                 bigquery_conn_id='bigquery_default'):
        super(BigQueryHook, self).__init__(
            conn_id=bigquery_conn_id)


    def client(self):

        """
        Returns a BigQuery PEP 249 connection object.
        """
        project = self._get_field('project')
        json_key_file = self._get_field('key_path')

        logging.info('project: %s', project)
        logging.info('json_key_file: %s', json_key_file)
        return get_client(project_id=project,
                          json_key_file=json_key_file,
                          readonly=False)


    def execute_query(self,
                      sql,
                      use_legacy_sql=False):


        job_id, _results=self.client().query(query=sql,
                                             use_legacy_sql=use_legacy_sql)

        return job_id

    def fetchone(self, job_id):


        complete = False
        sec = 0
        while not complete:
            complete, row_count = self.client().check_job(job_id)
            time.sleep(1)
            sec += 1

        results = self.client().get_query_rows(job_id)

        if complete:
            logging.info("Query completed in {} sec".format(sec))
        else:
            logging.info("Query failed")

        logging.info('results: %s', results[0])

        return results[0]

    def write_to_table(self,
                       sql,
                       destination_dataset,
                       destination_table,
                       use_legacy_sql = False,
                       write_disposition='WRITE_TRUNCATE'
                       ):

        job = self.client().write_to_table(query=sql,
                                           dataset=destination_dataset,
                                           table=destination_table,
                                           use_legacy_sql=use_legacy_sql,
                                           write_disposition=write_disposition,
                                           maximum_billing_tier=5
                                           )
        try:
            job_resource = self.client().wait_for_job(job, timeout=600)
            logging.info("Job completed: {}".format(job_resource))

        except BigQueryTimeoutException:
            logging.info("Query Timeout")

    def export_to_gcs(self,
                      dataset,
                      table,
                      gcs_uri):



        job = self.client().export_data_to_uris( [gcs_uri],
                                                 dataset,
                                                 table,
                                                 destination_format='NEWLINE_DELIMITED_JSON')
        try:
            job_resource = self.client().wait_for_job(job, timeout=600)
            logging.info('Export job: %s', job_resource)
        except BigQueryTimeoutException:
            logging.info('Timeout occured while exporting table %s.%s to %s',
                         dataset,
                         table,
                         gcs_uri)

class SstGcsExportOperator(BaseOperator):
    """
    Exports data from BQ table to GCS
    """
    ui_color = '#8033FF'
    template_fields = ('source_table',
                       'gcs_uri')

    @apply_defaults
    def __init__(self,
                 source_table,
                 gcs_uri,
                 bigquery_conn_id='bigquery_default',
                 *args, **kwargs):
        self.source_table = source_table
        self.gcs_uri = gcs_uri
        self.bigquery_conn_id = bigquery_conn_id

        super(SstGcsExportOperator, self).__init__(*args, **kwargs)

    def execute(self, context):
        logging.info('Exporting to %s from %s',
                     self.gcs_uri,
                     self.source_table)

        hook = BigQueryHook(bigquery_conn_id=self.bigquery_conn_id)

        source_table_split = self.source_table.split('.')

        hook.export_to_gcs(dataset=source_table_split[1],
                           table=source_table_split[2],
                           gcs_uri=self.gcs_uri)


class SstLoadDataOperator(BaseOperator):
    """
    Creates a daily partition in BigQuery table,
    based on provided execution time and SQL.
    With option to create a shard instead of partition
    """
    ui_color = '#33F3FF'
    template_fields = ('sql',
                       'destination_table',
                       'partition')
    template_ext = ('.sql',)

    @apply_defaults
    def __init__(self,
                 sql,
                 destination_table,
                 partition = None,
                 bigquery_conn_id='bigquery_default',
                 use_legacy_sql=False,
                 shard = False,
                 write_disposition = 'WRITE_TRUNCATE',
                 *args, **kwargs):
        self.sql = sql
        self.destination_table = destination_table
        self.partition = partition
        self.bigquery_conn_id=bigquery_conn_id
        self.use_legacy_sql=use_legacy_sql
        self.shard = shard
        self.write_disposition = write_disposition
        super(SstLoadDataOperator, self).__init__(*args, **kwargs)

    def execute(self, context):
        logging.info('Writing data to %s from SQL: %s',
                     self.destination_table,
                     self.sql)

        #prepare parameters for passing to the BQ hook for execution

        #getting dataset name from destination_table
        dst_table_array = self.destination_table.split('.')
        table_name = dst_table_array[len(dst_table_array) - 1]
        dataset_name = dst_table_array[len(dst_table_array) - 2]
        #logging.info('partition: %s', partition)
        hook = BigQueryHook(bigquery_conn_id=self.bigquery_conn_id)

        hook.write_to_table(sql = self.sql,
                            destination_dataset = dataset_name,
                            destination_table = '{}{}{}'.format(table_name,
                                                                '_' if self.shard else '$',
                                                                self.partition.replace('-', '')) if self.partition else table_name,
                            write_disposition=self.write_disposition)


class SstLastUpdateOperator(BaseOperator):
    """
    Gets last loaded timestamp from a BigQuery table
    """
    ui_color = '#b4e6f0'

    @apply_defaults
    def __init__(self,
                 dataset_table,
                 timestamp_field='load_datetime',
                 last_execution_time=None,
                 bigquery_conn_id='bigquery_default',
                 *args, **kwargs):
        self.dataset_table = dataset_table
        self.timestamp_field = timestamp_field
        self.last_execution_time = last_execution_time
        self.bigquery_conn_id = bigquery_conn_id
        super(SstLastUpdateOperator, self).__init__(*args, **kwargs)

    def execute(self, context):

        hook = BigQueryHook(bigquery_conn_id=self.bigquery_conn_id)

        self.sql = 'select max({}) as {} from `{}`'.format(
            self.timestamp_field,
            self.timestamp_field,
            self.dataset_table
        )

        if self.partition:
            self.sql += " where _partitiontime = timestamp('{}')".format(
                self.execution_time
            )

        logging.info('Executing SQL: %s', self.sql)

        job_id = hook.execute_query(self.sql, use_legacy_sql=False)
        result =  hook.fetchone(job_id)

        if result:
            timestamp = datetime.fromtimestamp(result[self.timestamp_field]).strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp = '1970-01-01'

        logging.info('Last Update Timestamp: %s', timestamp)

        return timestamp

class BigQueryPlugin(AirflowPlugin):
    name = "SST AirFlow Plugin"
    operators = [SstLastUpdateOperator,
                 SstLoadDataOperator,
                 SstGcsExportOperator]