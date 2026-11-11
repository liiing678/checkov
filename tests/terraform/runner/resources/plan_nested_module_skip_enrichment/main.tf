module "outer" {
  # checkov:skip=CKV_AWS_1:skip applies to every resource inside the outer module
  source = "./outer"
}
