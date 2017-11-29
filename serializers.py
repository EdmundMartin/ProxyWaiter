from marshmallow import Schema, fields


class AddProxySchema(Schema):
    proxy = fields.String(required=True)
    geo_location = fields.String(required=True)
    working = fields.Bool(required=True)


class DeleteProxySchema(Schema):
    proxy = fields.String(required=True)