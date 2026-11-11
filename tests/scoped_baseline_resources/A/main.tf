resource "aws_s3_bucket" "logs" {
  bucket = "tf-test-bucket-logs-A"
  acl    = "log-delivery-write"
}
