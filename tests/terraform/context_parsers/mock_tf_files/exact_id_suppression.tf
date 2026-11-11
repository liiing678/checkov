resource "aws_s3_bucket" "near_id_single" {
  # checkov:skip=CKV_AWS_1:only the single-digit check is skipped
  bucket = "near-id-single"
}

resource "aws_s3_bucket" "near_id_multi" {
  # checkov:skip=CKV_AWS_1,CKV_AWS_10:two exact IDs in one comment
  # checkov:skip=CKV_AWS_100:the three-digit check is skipped separately
  bucket = "near-id-multi"
}

resource "aws_s3_bucket" "bridgecrew_id" {
  # bridgecrew:skip=BC_AWS_IAM_5:bridgecrew id with a reason
  bucket = "bridgecrew-id"
}

resource "aws_s3_bucket" "no_suppression" {
  bucket = "no-suppression"
}
