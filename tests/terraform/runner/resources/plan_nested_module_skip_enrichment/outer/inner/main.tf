resource "aws_s3_bucket" "test-bucket1" {
  bucket = "test-bucket1"
  acl    = "public-read"
}
