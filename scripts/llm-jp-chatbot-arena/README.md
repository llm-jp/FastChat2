# Hosting Chatbot Arena on AWS

## General setup

### Key pair

Create a key pair for the web server.

```bash
KEY_NAME="chatbot-arena-key"
aws ec2 create-key-pair --key-name $KEY_NAME --query 'KeyMaterial' --output text >! ~/.ssh/chatbot-arena-key.pem
chmod 400 ~/.ssh/chatbot-arena-key.pem
```

### VPC

Create a VPC.

```bash
VPC_ID=$(aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=ChatbotArenaVPC}]' \
    --query 'Vpc.VpcId' \
    --output text)
```

### Security group

Create a security group for the web server, allowing ports 22, 80, and 443. Additionally, allow all traffic within the security group.

```bash
SG_NAME="chatbot-arena-sg"
SG_ID=$(aws ec2 create-security-group \
    --group-name $SG_NAME \
    --description "Chatbot Arena security group" \
    --vpc-id $VPC_ID \
    --query "GroupId" \
    --output text)

aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol all --source-group $SG_ID
```

### Subnet

Create a public subnet in the VPC.

```bash
PUBLIC_SUBNET_NAME="ChatbotArenaPublicSubnet"
PUBLIC_SUBNET_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --availability-zone us-west-2d \
    --cidr-block 10.0.0.0/20 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$PUBLIC_SUBNET_NAME}]" \
    --query 'Subnet.SubnetId' \
    --output text)

PUBLIC_SUBNET_NAME_A="ChatbotArenaPublicSubnetAZA"
PUBLIC_SUBNET_ID_A=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --availability-zone us-west-2a \
    --cidr-block 10.0.16.0/20 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$PUBLIC_SUBNET_NAME_A}]" \
    --query 'Subnet.SubnetId' \
    --output text)
```

Create a private subnet in the VPC.

```bash
PRIVATE_SUBNET_NAME="ChatbotArenaPrivateSubnet"
PRIVATE_SUBNET_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --availability-zone us-west-2d \
    --cidr-block 10.0.128.0/20 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$PRIVATE_SUBNET_NAME}]" \
    --query 'Subnet.SubnetId' \
    --output text)

PRIVATE_SUBNET_NAME_A="ChatbotArenaPrivateSubnetAZA"
PRIVATE_SUBNET_ID_A=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --availability-zone us-west-2a \
    --cidr-block 10.0.144.0/20 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$PRIVATE_SUBNET_NAME_A}]" \
    --query 'Subnet.SubnetId' \
    --output text)
```

### Internet gateway

Create an internet gateway and attach it to the VPC for the public subnet.

```bash
IGW_NAME="ChatbotArenaIGW"
IGW_ID=$(aws ec2 create-internet-gateway \
    --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=$IGW_NAME}]" \
    --query 'InternetGateway.InternetGatewayId' \
    --output text)

aws ec2 attach-internet-gateway \
    --internet-gateway-id $IGW_ID \
    --vpc-id $VPC_ID
```

Create and associate a route table for the public subnet.

```bash
PUBLIC_RT_NAME="ChatbotArenaPublicRouteTable"
PUBLIC_RT_ID=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=$PUBLIC_RT_NAME}]" \
    --query 'RouteTable.RouteTableId' \
    --output text)

aws ec2 create-route \
    --route-table-id $PUBLIC_RT_ID \
    --destination-cidr-block 0.0.0.0/0 \
    --gateway-id $IGW_ID

aws ec2 associate-route-table \
    --route-table-id $PUBLIC_RT_ID \
    --subnet-id $PUBLIC_SUBNET_ID_A

aws ec2 associate-route-table \
    --route-table-id $PUBLIC_RT_ID \
    --subnet-id $PUBLIC_SUBNET_ID

aws ec2 associate-route-table \
    --route-table-id $PRIVATE_RT_ID \
    --subnet-id $PRIVATE_SUBNET_ID_A
```

### NAT gateway

Create a NAT gateway and associate it with the public subnet.

```bash
NAT_EIP_ALLOC_ID=$(aws ec2 allocate-address \
    --domain vpc \
    --query 'AllocationId' \
    --output text)

NAT_GW_NAME="ChatbotArenaNATGateway"
NAT_GW_ID=$(aws ec2 create-nat-gateway \
    --subnet-id $PUBLIC_SUBNET_ID \
    --allocation-id $NAT_EIP_ALLOC_ID \
    --tag-specifications "ResourceType=natgateway,Tags=[{Key=Name,Value=$NAT_GW_NAME}]" \
    --query 'NatGateway.NatGatewayId' \
    --output text)

aws ec2 wait nat-gateway-available \
    --nat-gateway-ids $NAT_GW_ID
```

Create and associate a route table for the private subnet.

```bash
PRIVATE_RT_NAME="ChatbotArenaPrivateRouteTable"
PRIVATE_RT_ID=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=$PRIVATE_RT_NAME}]" \
    --query 'RouteTable.RouteTableId' \
    --output text)

aws ec2 create-route \
    --route-table-id $PRIVATE_RT_ID \
    --destination-cidr-block 0.0.0.0/0 \
    --nat-gateway-id $NAT_GW_ID

aws ec2 associate-route-table \
    --route-table-id $PRIVATE_RT_ID \
    --subnet-id $PRIVATE_SUBNET_ID
```

### Web server

Create an EC2 instance with the following settings:
- Ubuntu Server 22.04 LTS
- t2.xlarge
- 32GB storage

```bash
AMI_ID="ami-0606dd43116f5ed57"

SECURITY_GROUP_NAME="chatbot-arena-sg"
SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SECURITY_GROUP_NAME}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text)

PUBLIC_SUBNET_NAME="ChatbotArenaPublicSubnet"
PUBLIC_SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=${PUBLIC_SUBNET_NAME}" \
  --query 'Subnets[0].SubnetId' \
  --output text)

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type t2.xlarge \
    --key-name chatbot-arena-key \
    --security-group-ids $SECURITY_GROUP_ID \
    --subnet-id $PUBLIC_SUBNET_ID \
    --associate-public-ip-address \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":128,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ChatbotArenaWebServer}]' \
    --query 'Instances[0].InstanceId' \
    --output text)
```

### Model server

```bash
SECURITY_GROUP_NAME="chatbot-arena-sg"
SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SECURITY_GROUP_NAME}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text)

PRIVATE_SUBNET_NAME="ChatbotArenaPrivateSubnet"
PRIVATE_SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=${PRIVATE_SUBNET_NAME}" \
  --query 'Subnets[0].SubnetId' \
  --output text)
```

#### trn1.32xlarge

```bash
AMI_ID="ami-033430d109d6d84ff"
INSTANCE_TYPE="trn1.32xlarge"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name chatbot-arena-key \
    --security-group-ids $SECURITY_GROUP_ID \
    --subnet-id $PRIVATE_SUBNET_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":512,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ChatbotArenaModelServer99}]' \
    --query 'Instances[0].InstanceId' \
    --output text)
```

### inf2.48xlarge

```bash
AMI_ID="ami-033430d109d6d84ff"
INSTANCE_TYPE="inf2.48xlarge"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name chatbot-arena-key \
    --security-group-ids $SECURITY_GROUP_ID \
    --subnet-id $PRIVATE_SUBNET_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":512,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ChatbotArenaModelServer99}]' \
    --query 'Instances[0].InstanceId' \
    --output text)
```

### inf2.24xlarge

```bash
AMI_ID="ami-033430d109d6d84ff"
INSTANCE_TYPE="inf2.24xlarge"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name chatbot-arena-key \
    --security-group-ids $SECURITY_GROUP_ID \
    --subnet-id $PRIVATE_SUBNET_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":512,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ChatbotArenaModelServer99}]' \
    --query 'Instances[0].InstanceId' \
    --output text)
```

### Model server (g6.48xlarge)

```bash
AMI_ID="ami-025fbfd2a07cc6c2a"
INSTANCE_TYPE="g6.48xlarge"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name chatbot-arena-key \
    --security-group-ids $SECURITY_GROUP_ID \
    --subnet-id $PRIVATE_SUBNET_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":512,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ChatbotArenaModelServer99}]' \
    --query 'Instances[0].InstanceId' \
    --output text)
```

### Model server (g6.24xlarge)

```bash
AMI_ID="ami-025fbfd2a07cc6c2a"
INSTANCE_TYPE="g6.24xlarge"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name chatbot-arena-key \
    --security-group-ids $SECURITY_GROUP_ID \
    --subnet-id $PRIVATE_SUBNET_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":512,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ChatbotArenaModelServer99}]' \
    --query 'Instances[0].InstanceId' \
    --output text)
```
