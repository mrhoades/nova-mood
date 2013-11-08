#!/bin/bash

config_file=$1
output_base="/home/matty/benchmark_results"
sysbench_basedir="/opt/sysbench"
tpcc_mysql_basedir="/opt/tpcc-mysql"

sysbench_tests="${sysbench_basedir}/sysbench/tests/"
sysbench_bin="${sysbench_basedir}/sysbench/sysbench"

tpcc_load_bin="${tpcc_mysql_basedir}/tpcc_load"
tpcc_start_bin="${tpcc_mysql_basedir}/tpcc_start"

function distribute_ssh_key() {
  host_name=$1
  # These are ssh keys that are only used by this script, so it won't be dependent on the user's ssh agent.
  private_key="-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAufSBz+9oVxeK4/KjqTZQCI3jrk689gtBDT95AxyPT4c0Q/A3
uFYSESUTmazTaY949DZxa8JJswDA6NW7JfXO6BusgnxvPLYVXMtvKyioSP2KP5mi
EpSkPIzMe7bSXdJ16EY6X7oyuXJVDboyuVUnH78OFjQWJGeTGzwI12q07k6wh/zl
WHoKdsGUnolYJc8HASzX3q/0yLoHP9NZLGvXWDm4+C/m3Rhg3caPdDffGqBysNsa
gk2cx9Nh0uQVTn5sAcbpJzBEIAKinZfl6BmJQPQ903kGTa1EZWY/AS2Z0r/8tJOB
+qvXly5JMED+Aa6Zx9EhSpAjVs+qWTNHC7MYkQIDAQABAoIBAQCZ7eaPI9SxU1Gr
g60qY0U474trPM56tbIxrzsS8k9HO9pt6qmVM9pcyt5AtamDljo/ndmhpACx5ovJ
sTLsJ2ARDudsVGkYTnm8iMILbepwEUChiSF6VAToAn06Y4ocFB16GrgzicR3ckcp
x9o5RF3Qj6yvgIpbtEk3oCiJeVEwehRGzdE958uAeHVD7JfqqrGQkva2kyd/5dpD
aRCnIGpuM65jxqynDcSN4Qr22Lhycrf4y6NwS1cB7WdeVm6WHWGRjQflBSvr8S7R
DefNaMYeADgHHyqBJORuRw5mfWxLLdCushKieIK0m85ucxXGZMLZy+Pzt0MPbcAW
H7LEDKFhAoGBAO6lmh60LtXzHqErqSX6HL9eza5sb/aUvHcmnWAIwNhzivYJ7Jlr
6d7S4hD4YqogcK+ba05vgn+qiEbQkl6MdObKYBocbX+KFnFx0z2xW6Mtmgd5YlO/
UgXHX/nmEdDA7CXOoyji/ZRt6pB2szJkhsQgs7UPg8lh2Rzf79M7ZgT1AoGBAMd6
DPek4ipUX01Z7q8JPt+a4Ckz/VCNYPrTEBvGbU/4bQ2Cu7BcYPlDKZzJ+q2ksY7W
o7acuRdBy/tYtEcdo/ilRgPbDDoqcJwvV3oJuIfm1S/CDLk3utUgJ7baLWlZR81d
Fl3YuarF/GxyiWyzVPXQa66eL71LuIoJ9vR2G2OtAoGAA+dRjg8EdRt09M3yBl0A
+2BhnOjJLA9ixdAr4tZB0UiSjVO8OwY43Rw19nEZrA67ySORrcbFK7FuaTogKsvB
XcURrVuprtxjYZerDOdJyHGGg3jI0vXeMZoBR+UrhW6ibjvjD1gnLbZej95hMAHU
8oBWcC/AyBqBoqdHFP1zvcECgYBg+q+PPnROTBLBUnW+V2pf37YXkhUXsoRxrWdp
eYDvnkG2jdaeGWt0A/kZJwFepnFElomlYHCEJBL9sdSDtp9fZUqy2S4KoVN6O3H1
/P/f4pPG0jrJWZTVxPpJ5ayqSSOlbhpPqewqYHMmblDtrgoiMCAKFxHyn/up8MpF
c55BSQKBgCoZiOU7HE4S2KLJR4L6jW2eRFt6uqZA4TQgIKFVSCy/tvkwLn02FdRA
0LJQTNhzp9E7GEId7bRQ7mUq6pzToY2H4yPQKGeGekD81O39xM2xxH8RTvSsm136
DvJfTYA9XhMSIhY8AoS7gCOTYk6xLWgi49ulu2VqnTuR8ajjR8FU
-----END RSA PRIVATE KEY-----
"
  public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC59IHP72hXF4rj8qOpNlAIjeOuTrz2C0ENP3kDHI9PhzRD8De4VhIRJROZrNNpj3j0NnFrwkmzAMDo1bsl9c7oG6yCfG88thVcy28rKKhI/Yo/maISlKQ8jMx7ttJd0nXoRjpfujK5clUNujK5VScfvw4WNBYkZ5MbPAjXarTuTrCH/OVYegp2wZSeiVglzwcBLNfer/TIugc/01ksa9dYObj4L+bdGGDdxo90N98aoHKw2xqCTZzH02HS5BVOfmwBxuknMEQgAqKdl+XoGYlA9D3TeQZNrURlZj8BLZnSv/y0k4H6q9eXLkkwQP4BrpnH0SFKkCNWz6pZM0cLsxiR ubuntu@ci-test-bootvm"

  if [ ! -f /home/ubuntu/.ssh/id_rsa ]
  then
    echo "${private_key}" > /home/ubuntu/.ssh/id_rsa
    chmod 600 ${private_key}
  else
    grep -- "${private_key}" /home/ubuntu/.ssh/id_rsa
    if [ $? -ne 0 ]
    then
      echo "This script expects to be able to use it's own ssh keys, but a private key in /home/ubuntu/.ssh/id_rsa already exists, and it's not the script's key."
      exit 1
    fi
  fi

  if [ ! -f /home/ubuntu/.ssh/id_rsa.pub ]
  then
    echo "${public_key}" > /home/ubuntu/.ssh/id_rsa.pub
  else
    grep -- "${public_key}" /home/ubuntu/.ssh/id_rsa.pub
    if [ $? -ne 0 ]
    then
      echo "This script expects to be able to use it's own ssh keys, but a public key in /home/ubuntu/.ssh/id_rsa.pub alread exists, and it's not the script's key."
      exit 1
    fi
  fi

  ssh -A ${host_name} "grep ubuntu@percona-client-vm /home/ubuntu/.ssh/authorized_keys" > /dev/null 2>&1
  if [ $? -ne 0 ]
  then
    ssh -A ${host_name} "echo ${public_key} | tee -a /home/ubuntu/.ssh/authorized_keys" > /dev/null 2>&1
    if [ $? -ne 0 ]
    then
      echo "Failed to add this script's public ssh key to host ${host_name}."
      exit 1
    fi
  fi
}

function usage() {
  echo "Usage: $0 config_file"
}

function configure_ssh() {
  echo "Host *
  StrictHostKeyChecking no" > .ssh/config
}

function purge_binary_logs() {
  db_host=$1
  ssh ${db_host} "mysql -e \"purge binary logs before now();\""
  if [ $? -ne 0 ]
  then
    echo "Failed to purge binary logs."
    exit 1
  fi
}

function check_user() {
  user_name=`id -un`
  if [[ k${user_name} != k'ubuntu' ]]
  then
    echo "This script supposed to run as ubuntu user from a HP cloud instance."
    usage
    exit 1
  fi
}

function check_config() {
  if [ ! -f ${config_file} ]
  then
    echo "Config file not found."
    usage
    exit 1
  fi
}

function sanity_checks() {
  # check_user
  check_config

  if [ ! -d ${output_base} ]
  then
    mkdir -p ${output_base}
  fi
}

function install_packages() {
  host_name=$1
  ssh ${host_name} "sudo apt-get -y install sysstat bzr"
}

function install_data_collection_scripts() {
  host_name=$1
  data_collection_scripts_dir="./data_collection_scripts"
  if [ ! -d ${data_collection_scripts_dir} ]
  then
    echo "No data collection scripts for found, it should be ${data_collection_scripts_dir}."
    exit 1
  else
    scp -r ${data_collection_scripts_dir} ${host_name}:~
    if [ $? -ne 0 ]
    then
      echo "Failed to copy data collection scripts."
      exit 1
    fi
    ssh ${host_name} "chmod +x ${data_collection_scripts_dir}/*"
    if [ $? -ne -0 ]
    then
      echo "Failed to chmod +x data collection scripts on the database server."
      exit 1
    fi
  fi
}

function create_benchmark_database() {
  db_host=$1
  benchmark_type=$2
  oltp_table_size=$3
  oltp_tables_count=$4
  warehouses=$5

  case ${benchmark_type} in
    "sysbench")
      echo "drop database if exists sbtest; create database sbtest;
              grant all on sbtest.* to 'sbtest'@'%' identified by 'sbtest';
              grant all on sbtest.* to 'sbtest'@'localhost' identified by 'sbtest';" > /home/ubuntu/sb_init.sql
      scp /home/ubuntu/sb_init.sql ${db_host}:/home/ubuntu/
      ssh ${db_host} "mysql < /home/ubuntu/sb_init.sql"
      if [ $? -ne 0 ]
      then
        echo "Failed to create benchmark database for ${db_host} via ssh."
        exit 1
      fi

      ${sysbench_bin} \
        --test=${sysbench_tests}/db/parallel_prepare.lua \
        --mysql-user=sbtest \
        --mysql-password=sbtest \
        --mysql-host=${db_host} \
        --oltp_tables_count=${oltp_tables_count} \
        --oltp_table_size=${oltp_table_size} \
        --num-threads=4 \
        run > ${output_base}/prepare_sysbench_${db_host}_${oltp_table_size}_${oltp_tables_count}_`date +%s`.out
      if [ $? -ne 0 ]
      then
        echo "Failed to run sysbench prepare on ${db_host}."
        exit 1
      fi
    ;;
    "tpcc-mysql")
      ssh ${db_host} "ls /home/ubuntu/tpcc-mysql/add_fkey_idx.sql"
      if [ $? -ne 0 ]
      then
        ssh ${db_host} "bzr branch lp:~percona-dev/perconatools/tpcc-mysql"
        if [ $? -ne 0 ]
        then
          echo "Failed to get tpcc-mysql from bzr."
          exit 1
        fi
      fi
      echo "drop database if exists tpcc; create database tpcc;
            grant all on tpcc.* to 'tpcc'@'%' identified by 'tpcc';
            grant all on tpcc.* to 'tpcc'@'localhost' identified by 'tpcc';" > /home/ubuntu/tpcc_init.sql
      scp /home/ubuntu/tpcc_init.sql ${db_host}:/home/ubuntu/
      ssh ${db_host} "mysql < /home/ubuntu/tpcc_init.sql"
      ssh ${db_host} "mysql tpcc < /home/ubuntu/tpcc-mysql/create_table.sql"
      # single threaded load command: beware of slowness
      #${tpcc_load_bin} ${db_host} tpcc tpcc tpcc ${warehouses} > ${output_base}/tpcc_load_${db_host}_w${warehouses}_`date +%s`.out
      cd /opt/tpcc-mysql
      # separate script for parallel-loading of tpcc-mysql data, slightly modified for the original parallel loading script
      ./load.sh tpcc ${warehouses} ${db_host} > ${output_base}/tpcc_load_${db_host}_w${warehouses}_`date +%s`.out
      cd -
      ssh ${db_host} "mysql tpcc < /home/ubuntu/tpcc-mysql/add_fkey_idx.sql"

      if [ $? -ne 0 ]
      then
        echo "Failed to load tpcc database."
        exit 1
      fi
    ;;
    *)
      echo "Unknown benchmark type (so can't create user for that)."
      exit 1
    ;;
  esac

}

function start_collection() {
  db_host=$1
  benchmark_name=$2

  purge_binary_logs ${db_host}

  install_data_collection_scripts ${db_host}

  if [ ! -d ${output_base}/${benchmark_name} ]
  then
    mkdir -p ${output_base}/${benchmark_name}
    if [ $? -ne 0 ]
    then
      echo "Failed to create directory for benchmark ${benchmark_name}."
      exit 1
    fi
  fi

  bm_dir="${output_base}/${benchmark_name}"

  ssh ${db_host} "mpstat 1" > ${bm_dir}/mpstat.out &
  echo $! > /tmp/pid_${benchmark_name}_db_mpstat
  mpstat 1 > ${bm_dir}/mpstat_bm.out &
  echo $! > /tmp/pid_${benchmark_name}_mpstat

  ssh ${db_host} "mpstat -P ALL 1" > ${bm_dir}/mpstat_all.out &
  echo $! > /tmp/pid_${benchmark_name}_db_mpstat_all
  mpstat -P ALL 1 > ${bm_dir}/mpstat_all_bm.out &
  echo $! > /tmp/pid_${benchmark_name}_mpstat_all

  ssh ${db_host} "vmstat 1" > ${bm_dir}/vmstat.out &
  echo $! > /tmp/pid_${benchmark_name}_db_vmstat
  mpstat 1 > ${bm_dir}/vmstat_bm.out &
  echo $! > /tmp/pid_${benchmark_name}_vmstat

  ssh ${db_host} "iostat -mx 1" > ${bm_dir}/iostat.out &
  echo $! > /tmp/pid_${benchmark_name}_db_iostat
  mpstat 1 > ${bm_dir}/iostat_bm.out &
  echo $! > /tmp/pid_${benchmark_name}_iostat

  ssh ${db_host} "/home/ubuntu/data_collection_scripts/collect_diskstats.sh" > ${bm_dir}/diskstats.out &
  echo $! > /tmp/pid_${benchmark_name}_collect_diskstats

  ssh ${db_host} "/home/ubuntu/data_collection_scripts/collect_query_resptime.sh" > ${bm_dir}/query_resptime.out &
  echo $! > /tmp/pid_${benchmark_name}_collect_query_resptime

  ssh ${db_host} "mysqladmin ext -i1" > ${bm_dir}/mysqladmin.out &
  echo $! > /tmp/pid_${benchmark_name}_db_mysqladmin
}

function stop_collection() {
  db_host=$1
  pkill -9 mpstat
  pkill -9 vmstat
  pkill -9 iostat
  pkill -9 mysqladmin
  kill -9 `ps -ef | grep [c]ollect | awk '{print $2}'`
  ssh ${db_host} "pkill -9 mpstat"
  ssh ${db_host} "pkill -9 vmstat"
  ssh ${db_host} "pkill -9 iostat"
  ssh ${db_host} "pkill -9 mysqladmin"
  ssh ${db_host} "kill -9 `ps -ef | grep [c]ollect | awk '{print $2}'`"
  rm -f /tmp/pid*

}

function do_sysbench() {
  db_host=$1
  benchmark_name=$2
  ro_rw=$3
  oltp_table_size=$4
  oltp_tables_count=$5
  threads=$6
  benchmark_time=$7

  if [ ${ro_rw} == "ro" ]
  then
    oltp_read_only="on";
  else
    oltp_read_only="off";
  fi

  ${sysbench_bin} \
    --test=${sysbench_tests}/db/oltp.lua \
    --mysql-user=sbtest \
    --mysql-password=sbtest \
    --mysql-host=${db_host} \
    --oltp-tables-count=${oltp_tables_count} \
    --oltp-table-size=${oltp_table_size} \
    --num-threads=${threads} \
    --max-requests=0 \
    --max-time=${benchmark_time} \
    --oltp-read-only=${oltp_read_only} \
    --report-interval=1 \
    run > ${output_base}/${benchmark_name}/sysbench.out 2>&1
}

function do_tpcc () {
  db_host=$1
  benchmark_name=$2
  warehouses=$3
  threads=$4
  benchmark_time=$5

  ${tpcc_start_bin} -h${db_host} -dtpcc -utpcc -ptpcc -w${warehouses} -i1 -l${benchmark_time} > ${output_base}/${benchmark_name}/tpcc.out 2>&1
}

function kill_collection() {
  kill -9 `ps -ef | egrep [m]pstat\|[v]mstat\|[i]ostat\|[m]ysqladmin\|[c]ollect_query_resptime\|[c]ollect_diskstats| awk '{print $2}'`
}

function cleanup() {
  stop_collection
  kill_collection
}

trap cleanup INT

if [ $# -ne 1 ]
then
  echo "Wrong parameters."
  usage
  exit 1
fi

sanity_checks
configure_ssh

benchmark_defs=`egrep -v ^\#\|^$ ${config_file}`
ifsold=${IFS}
# new input field separator is new line, one benchmark is defined in one row
IFS='
'
for benchmark_def in ${benchmark_defs}
do
  benchmark_type=`echo ${benchmark_def} | awk '{print $1}'`
  case ${benchmark_type} in
    "sysbench")
      ro_rw=`echo ${benchmark_def} | awk '{print $2}'`
      oltp_table_size=`echo ${benchmark_def} | awk '{print $3}'`
      oltp_tables_count=`echo ${benchmark_def} | awk '{print $4}'`
      threads=`echo ${benchmark_def} | awk '{print $5}'`
      benchmark_time=`echo ${benchmark_def} | awk '{print $6}'`
      hosts=`echo ${benchmark_def} | awk '{print $7}'`
      benchmark_name_prefix=`echo ${benchmark_def} | awk '{print $8}'`
      warehouses=0
    ;;
    "tpcc-mysql")
      warehouses=`echo ${benchmark_def} | awk '{print $2}'`
      threads=`echo ${benchmark_def} | awk '{print $3}'`
      benchmark_time=`echo ${benchmark_def} | awk '{print $4}'`
      hosts=`echo ${benchmark_def} | awk '{print $5}'`
      benchmark_name_prefix=`echo ${benchmark_def} | awk '{print $6}'`
      oltp_table_size=0
      oltp_tables_count=0
    ;;
    *)
      echo "Unknown benchmark type (incorrect benchmark definition)."
      exit 1
    ;;
  esac

  IFS="@"
  for db_host in ${hosts}
  do
    distribute_ssh_key ${db_host}
    install_packages ${db_host}
    create_benchmark_database ${db_host} ${benchmark_type} ${oltp_table_size} ${oltp_tables_count} ${warehouses}
  done

  for thread in ${threads}
  do
    for db_host in ${hosts}
    do
      case ${benchmark_type} in
        "sysbench")
          benchmark_name="${benchmark_name_prefix}_sysbench_${db_host}_${ro_rw}_th${thread}_ts${oltp_table_size}_tc${oltp_tables_count}_time${benchmark_time}"
          start_collection ${db_host} ${benchmark_name}
          do_sysbench ${db_host} ${benchmark_name} ${ro_rw} ${oltp_table_size} ${oltp_tables_count} ${thread} ${benchmark_time} &
          echo $! > /tmp/pid_waiton_${benchmark_name}
        ;;
        "tpcc-mysql")
          benchmark_name="${benchmark_name_prefix}_tpcc_${db_host}_w${warehouses}_th${thread}_time${benchmark_time}"
          start_collection ${db_host} ${benchmark_name}
          do_tpcc ${db_host} ${benchmark_name} ${warehouses} ${thread} ${benchmark_time} &
          echo $!> /tmp/pid_waiton_${benchmark_name}
        ;;
      esac
    done

    for db_host in ${hosts}
    do
      IFS=${ifsold}
      for current_benchmark in `cat /tmp/pid_waiton* | xargs`
      do
        wait ${current_benchmark}
      done
      IFS="@"
      stop_collection ${db_host}
    done
  done
  IFS=${ifsold}
done