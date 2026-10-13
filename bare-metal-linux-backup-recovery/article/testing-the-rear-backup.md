## Testing the ReaR Backup in a Virtual Machine

Creating a backup is only the first step in a disaster recovery strategy. Until that backup has been restored successfully, there is no certainty that it will work when needed.

To validate our ReaR backup, we performed a full operating system restoration in an Oracle VirtualBox virtual machine. This allowed us to reproduce the server's storage configuration, restore the operating system, and test its functionality without risking the production server.

The test used VirtualBox running on a Windows 10 PC, although neither Windows nor VirtualBox is a requirement. The same approach can be followed using another supported host operating system or hypervisor, with adjustments for the virtual hardware configuration.

### Preparing the Recovery Environment

Two files were required from the same ReaR backup set:

- `rear-server.iso` — The bootable recovery environment, containing the information needed to reconstruct the server's storage layout.
- `backup.tar.gz` — The compressed archive containing the operating system and files included in the backup.

We configured the VM with 8 GB RAM, four virtual CPUs, EFI firmware, and four virtual NVMe disks matching the original server's disk capacities.

The production server uses software RAID, with two smaller NVMe disks containing the operating system and a second pair of larger disks supporting `/var/lib`. Reproducing this configuration was important because the test needed to validate ReaR's ability to reconstruct the original partitions, RAID arrays, and filesystems, rather than simply extract files onto an existing Linux installation.

An additional SATA virtual disk was created to hold the compressed backup archive during restoration. This disk was not part of the production server's storage configuration. In a real recovery, the backup archive would be accessible from OVH Backup Storage over NFS. Since this storage was not accessible from our VM, the additional virtual disk served as a local substitute, allowing the recovery environment to access the archive.

### Restoring the Backup

The restoration followed these main steps:

1. **Boot the recovery environment.** Start the VM using `rear-server.iso` and enter the ReaR recovery shell.
2. **Make the backup archive accessible.** Transfer `backup.tar.gz` from the Windows host to the temporary SATA disk, which substitutes for the production backup storage.
3. **Configure the backup location.** Mount the staging disk and update the ReaR configuration to reference its local directory using `BACKUP_URL="file:///mnt/backup"`, retaining `BACKUP=NETFS`.
4. **Run the restoration.** Execute `rear -v recover`, checking that ReaR maps the original disks to the correct virtual disks and does not overwrite the temporary staging disk.
5. **Verify the restored storage and boot configuration.** Check the reconstructed RAID arrays, filesystems, mount points, and EFI configuration, resolving any issues before attempting to boot.
6. **Boot and test the restored operating system.** Remove the recovery ISO, boot AlmaLinux from the restored disks, adapt the network configuration for the virtual environment, and check that the expected system services operate.

The restoration involved reconstructing the storage layout and extracting an archive of approximately 200 GB. The procedure was therefore more involved than restoring a small system image, particularly because the virtual disks needed to represent the original software RAID configuration.

### Problems Encountered

The test was successful, but several issues required investigation and corrective action.

#### ReaR Version and RAID Compatibility

An earlier attempt using ReaR 2.6 exposed a problem with the RAID layout. We upgraded the production server to ReaR 2.9 and regenerated the recovery files. The updated recovery environment allowed us to proceed with the restoration.

This highlighted the importance of testing the actual recovery media. Updating the installed ReaR package does not correct an ISO generated using an earlier version.

#### Accessing the Backup Archive

The approximately 200 GB backup archive had to be accessible from the recovery environment. Initial attempts with SMB access and VirtualBox's virtual ISO (VISO) feature, hoping to make the archive available directly from the Windows host without creating an additional copy, proved unsuccessful.

Ultimately, we set up a local HTTP server on the Windows host using a simple PowerShell script, without requiring any additional server software or complex configuration. This allowed us to transfer the archive to a temporary virtual disk, which served as the local substitute for OVH Backup Storage. Once downloaded, the archive could be accessed through a local filesystem, allowing ReaR's NETFS restoration process to proceed without changing the original production backup configuration.

#### EFI Filesystem Repair and Service Startup

The EFI partition required a FAT filesystem repair before it could be mounted successfully. However, the necessary `fsck.fat` utility was not included in the minimal ReaR rescue environment. Although the operating system's files had already been restored, AlmaLinux was not yet bootable, so we had to manually assemble and mount the restored filesystems, prepare access to the restored system environment, and locate the utility within the AlmaLinux installation. Only then could we perform the repair and proceed with the recovery.

While working within the restored system, we also took the opportunity to disable the automatic startup of MariaDB, Docker, and related services. Their data directories under `/var/lib` had deliberately been excluded from the ReaR backup and would be restored separately at a later stage. Disabling these services prevented them from attempting to start without their required data when the recovered operating system was first booted.

These issues demonstrate why a recovery test is valuable. Problems involving storage reconstruction, backup accessibility, and boot configuration are much easier to investigate in a controlled environment than during an actual server outage.

### Verifying the Restored System

The final objective was to establish that the backup could restore a bootable and functional operating system, not merely that ReaR could extract its archive.

Following the restoration, we successfully booted the recovered AlmaLinux installation and verified the reconstructed storage configuration.

We then adapted the virtual machine's network settings and Apache configuration to use a local test IP address instead of the production server's address.

This allowed us to test the restored Apache virtual host and PHP execution through a browser.

The application returned an *"Error establishing a database connection"* message. In this case, that was the expected result because `/var/lib/mysql` had deliberately been excluded from the ReaR backup.

The error demonstrated that Apache was serving the restored application and PHP was executing. It did not indicate a failed operating system recovery, nor did it establish that the complete application was functional.

The test also included checks of the restored Webmin/Virtualmin administration environment, which worked in the VM.

### What the Test Demonstrated

The successful restoration confirmed several important aspects of our backup strategy:

- The ReaR recovery ISO could boot independently of the original physical server.
- The original partition layout, software RAID arrays, and filesystems could be reconstructed using virtual hardware.
- The NETFS archive contained the files necessary to restore the operating system.
- AlmaLinux could boot from the restored virtual disks.
- Apache, PHP, and the restored web server configuration remained usable after adjusting the network settings.
- The backup could be restored without modifying or interrupting the production server.

**The test validated ReaR as a working operating system backup and recovery method for this server configuration.** It also demonstrated that recovery onto different hardware is feasible, provided the storage and boot environment can be accommodated.

There are, however, important limitations. The test did not include restoring MariaDB data or Docker application data, both of which are deliberately handled separately in our backup strategy. Nor does a successful virtual restoration guarantee that recovery on every physical server will be identical.

A complete production recovery would still require restoring those excluded datasets, validating application functionality, and making any necessary hardware and network adjustments.

Nevertheless, the exercise significantly increased our confidence in the recovery strategy. Rather than relying on the existence of an ISO and a compressed archive, we now have practical evidence that the operating system can be reconstructed and started on an independent machine.

For a detailed, repeatable procedure, see the [ReaR VM Recovery Test Guide](../guides/).
