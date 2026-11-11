resource "aws_s3_bucket" "logs" {
  bucket = "tf-test-bucket-logs-B"
  acl    = "log-delivery-write"
}
