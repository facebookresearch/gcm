# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
GRAPH_API_ACCESS_TOKEN = ENV['GRAPH_API_ACCESS_TOKEN']
SYSTEMD_OUT = "/lib/systemd/system"

Vagrant.configure("2") do |config|
    config.vm.box = "generic/debian12"

    config.vm.synced_folder ".", "/vagrant"

    config.vm.provision "shell", inline: <<-SHELL
      # install GCM
      cd /vagrant
      sudo chmod 007 gcm_*.deb
      sudo dpkg -i gcm_*.deb
      cd ..

      # Create user and give admin power
      sudo useradd cluster_monitor
      sudo usermod -a -G sudo cluster_monitor

      # Copy fake commands
      cp /vagrant/gcm/tests/systemd/commands/sacct /usr/local/bin/sacct
      cp /vagrant/gcm/tests/data/sample-sacct-multiple-multiline.txt /usr/local/bin/sample-sacct-output.txt
      cp /vagrant/gcm/tests/systemd/commands/sinfo /usr/local/bin/sinfo
      cp /vagrant/gcm/tests/data/sample-sinfo-output.txt /usr/local/bin/sample-sinfo-output.txt
      cp /vagrant/gcm/tests/systemd/commands/sacctmgr_qos /usr/local/bin/sacctmgr_qos
      cp /vagrant/gcm/tests/data/sample-sacctmgr-qos.txt /usr/local/bin/sample-sacctmgr-qos.txt
      cp /vagrant/gcm/tests/systemd/commands/squeue /usr/local/bin/squeue
      cp /vagrant/gcm/tests/data/sample-squeue-output.txt /usr/local/bin/sample-squeue-output.txt
      cp /vagrant/gcm/tests/systemd/commands/scontrol /usr/local/bin/scontrol
      cp /vagrant/gcm/tests/data/sample-scontrol-show-config-output.txt /usr/local/bin/sample-scontrol-output.txt

      # Make fake commands and gcm executable
      chmod +x /usr/local/bin/sacct
      chmod +x /usr/local/bin/sinfo
      chmod +x /usr/local/bin/sacctmgr_qos
      chmod +x /usr/local/bin/squeue
      chmod +x /usr/local/bin/scontrol

      # Create graph api key
      echo "#{GRAPH_API_ACCESS_TOKEN}" > /home/graph_api_key

      # Copy config file
      cp /vagrant/gcm/tests/systemd/files/sacct_backfill.service #{SYSTEMD_OUT}/sacct_backfill.service
      mkdir -p /etc/fb-gcm && cp /vagrant/gcm/tests/systemd/files/gcm_ci_config.toml $_/config.toml

      # Give users permission to execute script and binary
      sudo chmod +x /usr/bin/gcm
      sudo chmod +r /etc/fb-gcm/config.toml

      # Create and give permission to log folders
      sudo mkdir /var/log/sacct_backfill_logs
      sudo mkdir /var/log/sacct_publish_logs
      sudo chown cluster_monitor:cluster_monitor /var/log/sacct_backfill_logs
      sudo chown cluster_monitor:cluster_monitor /var/log/sacct_publish_logs

      # Set timezone
      sudo ln -fs /usr/share/zoneinfo/America/Los_Angeles /etc/localtime

    SHELL

end
