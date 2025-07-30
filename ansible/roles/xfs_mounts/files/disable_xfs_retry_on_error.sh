#!/bin/bash

for i in $(df -h | grep /mnt/MINIODRIVE | awk '{ print $1 }'); do
      mountPath="$(df -h | grep $i | awk '{ print $6 }')"
      deviceName="$(basename $i)"
      echo "Modifying xfs max_retries and retry_timeout_seconds for drive $i mounted at $mountPath"
      echo 0 > /sys/fs/xfs/$deviceName/error/metadata/EIO/max_retries
      echo 0 > /sys/fs/xfs/$deviceName/error/metadata/ENOSPC/max_retries
      echo 0 > /sys/fs/xfs/$deviceName/error/metadata/default/max_retries
done
exit 0