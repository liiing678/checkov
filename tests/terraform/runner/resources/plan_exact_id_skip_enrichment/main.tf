resource "aws_s3_bucket" "test-bucket1" {
  # checkov:skip=CKV_AWS_1:only the single-digit check is skipped
  # checkov:skip=CKV_AWS_145:only the exact 145 check is skipped
  # checkov:skip=CKV_AWS_20,CKV_AWS_21:multiple exact IDs share one comment
  bucket = "test-bucket1"
  acl    = "public-read"
}

resource "aws_iam_policy" "policy" {
  name = "my_policy-123456789101"
  path = "/"
  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": ["*"],
            "Effect": "Allow",
            "Resource": "arn:aws:iam::123456789012:role/admin"
        }
    ]
}
EOF
}

resource "aws_dynamodb_table" "cross-environment-violations" {
  name          = "CrossEnvironmentViolations"
  read_capacity = 20
  write_capacity = 20
  hash_key      = "id"
  attribute {
    name = "id"
    type = "S"
  }
}
