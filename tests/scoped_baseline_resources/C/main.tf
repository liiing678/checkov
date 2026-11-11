resource "aws_s3_bucket" "logs" {
  bucket = "tf-test-bucket-logs-C"
  acl    = "log-delivery-write"
}
