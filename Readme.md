### Adblocking download and store filters task ###

This module contains a luigi task that

1. Download adblocking filters used by the adblocking module in the extension.
1. Store these filters to an S3 bucket along with their corresponding md5 and urls, so that the extension imports these filters directly from S3.

* In order to schedule the task on daily basis a cron task is triggered on the deployed instance.
* The filters are downloaded daily, for each day a new bucket is created in S3.
* These buckets are kept for one week in case of backtracking.
* They get deleted automatically after one week (This is done by adding a LIFE CYCLE RULE to the s3 bucket from the console).
* The (filters, md5s, urls) tuples are saved to filters_urls.txt file in the corresponding day bucket.

### Deploy for the very first time ###

Deployment involves creating an autoscaling group and the instance.
This section is for creating all of these for the first time.

1. `fab launch_cluster` instances get launched
1. `fab update` creates AMI out of each created instance, and creates one autoscaling group (and launch config) for each instance.
Our instances will NOT get attached to the autoscaling groups!!!
* Note: the commands to run whenever  new instance is created by auto-scale should be added to (fabfile > cliqs.setup > cluster > autoscale_launch_data), in this case we would like to restart the luigid central scheduler.
1. We created the instances before creating the autoscaling group, because creating autoscaling group involved taking AMI snapshots of the instances,
so they have to exist first.
Actually now we don't need the instances from step 1 anymore, they just served as a bootstrap to get autoscaling stuff created (AMI snapshot, launch config, autoscaling group). So we go to AWS Console and manually
terminate the instances, and delete their corresponding volumes manually.
1. But now we have no instances, because autoscaling group was created with MIN=0,Desired=0,Max=1. So go change autoscaling group params Min and Desired to 1 (from the console).
1. All set. Now test autoscaling user data (bootstrap script) by terminating an instances that was created by autoscaling.

### Deploy new code to existing cluster ###

1. Commit your code on the local repo, then `fab std.ec2.for_all deploy`
1. Now we need to update the AMI snapshot so that new instances created by autoscaling would pick the latest code we just deployed: `fab std.autoscale.update_config_from_instance:[instance id with updated code]`


Done :)
